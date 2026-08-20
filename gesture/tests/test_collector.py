"""Behavior tests for the Slice 5 collection/reference scaffold."""

import json

import cv2
import numpy as np
import pytest

from gesture.collect_dataset import (
    configure_capture,
    save_reference,
    validate_target_accepted,
)
from gesture.contracts import SessionMetadata


def test_capture_uses_mjpg_before_setting_frame_size():
    class FakeCapture:
        def __init__(self):
            self.calls = []

        def set(self, property_id, value):
            self.calls.append((property_id, value))
            return True

    capture = FakeCapture()
    configure_capture(capture, 640, 480)

    assert capture.calls == [
        (cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG")),
        (cv2.CAP_PROP_FRAME_WIDTH, 640),
        (cv2.CAP_PROP_FRAME_HEIGHT, 480),
    ]


def test_collection_target_must_be_positive():
    assert validate_target_accepted(None) is None
    assert validate_target_accepted(10) == 10
    with pytest.raises(ValueError):
        validate_target_accepted(0)


def test_session_metadata_records_model_path_and_hash():
    metadata = SessionMetadata(
        session_id="subject01-session01",
        subject_id="subject01",
        hand_scope="right",
        distance="medium",
        view_angle="frontal",
        lighting="indoor-day",
        background="office",
        camera_index=0,
        frame_width=640,
        frame_height=480,
        landmark_backend="MediaPipe Tasks HandLandmarker 1.0.1",
        landmark_model_path="/project/gesture/models/hand_landmarker.task",
        landmark_model_sha256="a" * 64,
    ).to_dict()
    assert metadata["landmark_model_path"].endswith("hand_landmarker.task")
    assert metadata["landmark_model_sha256"] == "a" * 64


def test_reference_capture_is_guidance_only_and_never_overwrites(tmp_path):
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    hand = {
        "handedness": "Right",
        "handedness_score": 0.99,
        "image_landmarks": np.zeros((21, 3), dtype=np.float32),
        "world_landmarks": np.zeros((21, 3), dtype=np.float32),
        "feature": np.zeros(63, dtype=np.float32),
    }
    model_path = tmp_path / "hand_landmarker.task"
    model_path.write_bytes(b"test model identity")

    metadata_path = save_reference(
        tmp_path / "references",
        "HOLD",
        "subject01",
        frame,
        hand,
        model_path,
        "b" * 64,
        "MediaPipe Tasks HandLandmarker 1.0.1",
    )
    payload = json.loads(metadata_path.read_text())
    assert payload["usage"] == "collection_guidance_only_not_training"
    assert payload["label"] == "HOLD"
    assert (metadata_path.parent / "hold.jpg").is_file()

    with pytest.raises(FileExistsError):
        save_reference(
            tmp_path / "references",
            "HOLD",
            "subject01",
            frame,
            hand,
            model_path,
            "b" * 64,
            "MediaPipe Tasks HandLandmarker 1.0.1",
        )
