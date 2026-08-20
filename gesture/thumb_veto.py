"""Deterministic semantic thumb-extension veto for AUTO_LAND commands."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


AUTO_LAND = "AUTO_LAND"
ALLOWED = "ALLOWED"
REJECTED_BY_THUMB_VETO = "REJECTED_BY_THUMB_VETO"


@dataclass(frozen=True)
class ThumbThreshold:
    """Train-only threshold and the evidence used to derive it."""

    value: float
    train_auto_land_samples: int
    required_allowed_samples: int
    observed_allowed_samples: int
    fit_scope: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "train_auto_land_samples": self.train_auto_land_samples,
            "required_allowed_samples": self.required_allowed_samples,
            "observed_allowed_samples": self.observed_allowed_samples,
            "observed_retention": (
                self.observed_allowed_samples / self.train_auto_land_samples
            ),
            "fit_scope": self.fit_scope,
            "policy": (
                "HIGHEST_TRAIN_AUTO_LAND_ORDER_STATISTIC_RETAINING_AT_LEAST_"
                "THE_CONFIGURED_FRACTION"
            ),
        }


def thumb_extension_components(feature: Sequence[float]) -> tuple[float, float]:
    """Return thumb IP straightness and palm-relative tip reach.

    The frozen 63D feature is reshaped to the canonical MediaPipe topology.
    Straightness is the MCP-to-tip chord divided by the MCP-to-IP-to-tip path:

        ||L4-L2|| / (||L3-L2|| + ||L4-L3||)

    Reach is the distance from thumb tip L4 to the centroid of wrist and the
    four finger MCP landmarks L0/L5/L9/L13/L17. Both values are invariant to
    translation, palm scale, in-plane rotation, and handedness after the frozen
    preprocessing transform.
    """

    points = np.asarray(feature, dtype=np.float64)
    if points.shape != (63,) or not np.isfinite(points).all():
        raise ValueError("thumb rule expects one finite 63D canonical feature")
    points = points.reshape(21, 3)
    proximal = float(np.linalg.norm(points[3] - points[2]))
    distal = float(np.linalg.norm(points[4] - points[3]))
    path_length = proximal + distal
    if path_length <= 1e-12:
        raise ValueError("degenerate thumb MCP-IP-tip geometry")
    straightness = float(np.linalg.norm(points[4] - points[2]) / path_length)
    palm_center = points[[0, 5, 9, 13, 17]].mean(axis=0)
    palm_reach = float(np.linalg.norm(points[4] - palm_center))
    return straightness, palm_reach


def thumb_extension_score(feature: Sequence[float]) -> float:
    """Return the single interpretable thumb-extension score."""

    straightness, palm_reach = thumb_extension_components(feature)
    return straightness * palm_reach


def derive_train_only_threshold(
    auto_land_features: np.ndarray, minimum_retention: float
) -> ThumbThreshold:
    """Choose the most conservative observed threshold meeting retention.

    Only TRAIN-fold AUTO_LAND samples may be supplied. No negative class or
    evaluation-fold observation participates in the threshold.
    """

    return derive_retention_threshold(
        auto_land_features,
        minimum_retention,
        fit_scope="TRAIN_FOLD_ONLY",
    )


def derive_retention_threshold(
    auto_land_features: np.ndarray,
    minimum_retention: float,
    *,
    fit_scope: str,
) -> ThumbThreshold:
    """Apply the frozen retention policy to an explicitly named fit scope."""

    if not fit_scope:
        raise ValueError("fit_scope must be explicit")
    features = np.asarray(auto_land_features, dtype=np.float64)
    if features.ndim != 2 or features.shape[1] != 63 or len(features) == 0:
        raise ValueError("threshold derivation expects a non-empty [N, 63] array")
    if not 0.0 < minimum_retention <= 1.0:
        raise ValueError("minimum_retention must be in (0, 1]")
    scores = np.sort(
        np.asarray([thumb_extension_score(row) for row in features], dtype=np.float64)
    )
    required_allowed = int(math.ceil(minimum_retention * len(scores)))
    first_allowed_index = len(scores) - required_allowed
    threshold = float(scores[first_allowed_index])
    observed_allowed = int(np.sum(scores >= threshold))
    if observed_allowed < required_allowed:
        raise AssertionError("derived threshold violated train retention contract")
    return ThumbThreshold(
        value=threshold,
        train_auto_land_samples=len(scores),
        required_allowed_samples=required_allowed,
        observed_allowed_samples=observed_allowed,
        fit_scope=fit_scope,
    )


def thumb_veto_status(
    predicted_label: str, extension_score: float, threshold: float
) -> str:
    """Apply the veto only to an AUTO_LAND prediction; never relabel it."""

    if not math.isfinite(extension_score) or not math.isfinite(threshold):
        raise ValueError("thumb score and threshold must be finite")
    if predicted_label == AUTO_LAND and extension_score < threshold:
        return REJECTED_BY_THUMB_VETO
    return ALLOWED
