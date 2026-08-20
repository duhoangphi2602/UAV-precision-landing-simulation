"""Frozen Slice 5 gesture and landmark data contracts."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Sequence

import numpy as np


DATASET_SCHEMA_VERSION = "gesture_dataset_v1"
PREPROCESSING_VERSION = "wrist-palm-canonical-v1"
GESTURE_CLASSES = (
    "TAKEOFF",
    "FORWARD",
    "BACKWARD",
    "LEFT",
    "RIGHT",
    "HOLD",
    "AUTO_LAND",
)
CLASS_KEYS = {str(index + 1): label for index, label in enumerate(GESTURE_CLASSES)}
GESTURE_POSE_DEFINITIONS = {
    "HOLD": "thumb, index, middle, ring, and pinky extended (open palm)",
    "TAKEOFF": "index, middle, ring, and pinky extended; thumb folded",
    "AUTO_LAND": "thumb and pinky extended; index, middle, and ring folded (shaka)",
    "FORWARD": "index extended; thumb, middle, ring, and pinky folded",
    "BACKWARD": "index and middle extended; ring and pinky folded; thumb relaxed/folded",
    "LEFT": "thumb extended; index, middle, ring, and pinky folded",
    "RIGHT": "pinky extended; thumb, index, middle, and ring folded",
}

# MediaPipe Hand Landmarker connections. Keeping the topology local makes the
# collector's preview independent from drawing-helper API changes.
HAND_CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
)

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class SessionMetadata:
    """Metadata that remains constant for one isolated recording session."""

    session_id: str
    subject_id: str
    hand_scope: str
    distance: str
    view_angle: str
    lighting: str
    background: str
    camera_index: int
    frame_width: int
    frame_height: int
    landmark_backend: str
    landmark_model_path: str
    landmark_model_sha256: str
    preprocessing_version: str = PREPROCESSING_VERSION
    schema_version: str = DATASET_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def validate_identifier(value: str, field_name: str) -> str:
    """Reject path-like or ambiguous subject/session identifiers."""

    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(
            f"{field_name} must match {_SAFE_IDENTIFIER.pattern!r}; got {value!r}"
        )
    return value


def validate_label(label: str) -> str:
    """Return a canonical gesture label or raise a useful error."""

    canonical = label.strip().upper()
    if canonical not in GESTURE_CLASSES:
        allowed = ", ".join(GESTURE_CLASSES)
        raise ValueError(f"unknown gesture label {label!r}; expected one of: {allowed}")
    return canonical


def normalize_landmarks(
    landmarks: Sequence[Sequence[float]], handedness: str
) -> np.ndarray:
    """Canonicalize 21 MediaPipe xyz landmarks into a 63-value feature vector.

    The transform removes image translation, palm scale, in-plane palm rotation,
    and left/right mirroring while retaining depth relative to palm scale.
    """

    points = np.asarray(landmarks, dtype=np.float32)
    if points.shape != (21, 3):
        raise ValueError(f"expected landmark shape (21, 3), got {points.shape}")
    if not np.isfinite(points).all():
        raise ValueError("landmarks contain NaN or infinity")

    canonical = points - points[0]
    hand = handedness.strip().lower()
    if hand not in {"left", "right"}:
        raise ValueError(f"handedness must be Left or Right, got {handedness!r}")
    if hand == "left":
        canonical[:, 0] *= -1.0

    palm_axis = canonical[9, :2]
    palm_scale = float(np.linalg.norm(palm_axis))
    if palm_scale <= 1e-6:
        raise ValueError("degenerate palm scale from wrist to middle-finger MCP")
    canonical /= palm_scale

    # Align wrist -> middle MCP with negative image Y (upright canonical hand).
    current_angle = math.atan2(float(canonical[9, 1]), float(canonical[9, 0]))
    rotation = -math.pi / 2.0 - current_angle
    cosine = math.cos(rotation)
    sine = math.sin(rotation)
    rotation_matrix = np.asarray(
        ((cosine, -sine), (sine, cosine)), dtype=np.float32
    )
    canonical[:, :2] = canonical[:, :2] @ rotation_matrix.T

    feature = canonical.reshape(63).astype(np.float32, copy=False)
    if not np.isfinite(feature).all():
        raise ValueError("normalized feature contains NaN or infinity")
    return feature


def feature_distance(first: np.ndarray, second: np.ndarray) -> float:
    """Return RMS feature motion used to reject adjacent near-duplicates."""

    lhs = np.asarray(first, dtype=np.float32)
    rhs = np.asarray(second, dtype=np.float32)
    if lhs.shape != (63,) or rhs.shape != (63,):
        raise ValueError("feature_distance expects two 63-value feature vectors")
    return float(np.sqrt(np.mean(np.square(lhs - rhs))))


class CaptureDecision(str, Enum):
    """Auditable reasons why a candidate frame is accepted or rejected."""

    ACCEPT = "ACCEPT"
    PAUSED = "PAUSED"
    NO_HAND = "NO_HAND"
    RATE_LIMITED = "RATE_LIMITED"
    NEAR_DUPLICATE = "NEAR_DUPLICATE"


@dataclass
class CaptureGate:
    """State machine enforcing deliberate, bounded, non-duplicate capture."""

    sample_hz: float
    min_feature_delta: float
    label: str = GESTURE_CLASSES[0]
    recording: bool = False
    capture_block_index: int = 0
    last_candidate_at: float = float("-inf")
    last_features: dict[str, np.ndarray] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sample_hz <= 0:
            raise ValueError("sample_hz must be positive")
        if self.min_feature_delta < 0:
            raise ValueError("min_feature_delta cannot be negative")
        self.label = validate_label(self.label)

    @property
    def sample_interval(self) -> float:
        return 1.0 / self.sample_hz

    def toggle_recording(self) -> bool:
        if not self.recording:
            self.capture_block_index += 1
        self.recording = not self.recording
        return self.recording

    def select_label(self, label: str) -> bool:
        """Select a label only while paused; return whether it changed."""

        if self.recording:
            return False
        self.label = validate_label(label)
        return True

    def evaluate(
        self, now: float, feature: np.ndarray | None
    ) -> CaptureDecision:
        if not self.recording:
            return CaptureDecision.PAUSED
        if feature is None:
            return CaptureDecision.NO_HAND
        if now - self.last_candidate_at < self.sample_interval:
            return CaptureDecision.RATE_LIMITED

        candidate = np.asarray(feature, dtype=np.float32)
        if candidate.shape != (63,) or not np.isfinite(candidate).all():
            raise ValueError("capture candidate must be a finite 63-value feature")
        self.last_candidate_at = now
        previous = self.last_features.get(self.label)
        if (
            previous is not None
            and feature_distance(previous, candidate) < self.min_feature_delta
        ):
            return CaptureDecision.NEAR_DUPLICATE

        self.last_features[self.label] = candidate.copy()
        return CaptureDecision.ACCEPT


def final_session_status(clean_exit: bool) -> str:
    """Map only an intentional clean quit to a complete collection session."""

    return "COMPLETE" if clean_exit else "ABORTED"
