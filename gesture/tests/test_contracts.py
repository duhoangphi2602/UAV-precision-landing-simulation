"""Unit tests for the frozen Slice 5 data contracts."""

import math

import numpy as np
import pytest

from gesture.contracts import (
    CaptureDecision,
    CaptureGate,
    GESTURE_CLASSES,
    GESTURE_POSE_DEFINITIONS,
    feature_distance,
    final_session_status,
    normalize_landmarks,
    validate_identifier,
    validate_label,
)


def sample_landmarks() -> np.ndarray:
    points = np.zeros((21, 3), dtype=np.float32)
    for index in range(21):
        points[index] = (0.4 + index * 0.004, 0.7 - index * 0.012, index * 0.001)
    points[0] = (0.4, 0.7, 0.0)
    points[9] = (0.45, 0.45, 0.01)
    return points


def test_gesture_class_order_is_frozen():
    assert GESTURE_CLASSES == (
        "TAKEOFF",
        "FORWARD",
        "BACKWARD",
        "LEFT",
        "RIGHT",
        "HOLD",
        "AUTO_LAND",
    )


def test_gesture_pose_topologies_are_frozen():
    assert GESTURE_POSE_DEFINITIONS == {
        "HOLD": "thumb, index, middle, ring, and pinky extended (open palm)",
        "TAKEOFF": "index, middle, ring, and pinky extended; thumb folded",
        "AUTO_LAND": "thumb and pinky extended; index, middle, and ring folded (shaka)",
        "FORWARD": "index extended; thumb, middle, ring, and pinky folded",
        "BACKWARD": "index and middle extended; ring and pinky folded; thumb relaxed/folded",
        "LEFT": "thumb extended; index, middle, ring, and pinky folded",
        "RIGHT": "pinky extended; thumb, index, middle, and ring folded",
    }


def test_normalization_is_translation_and_scale_invariant():
    points = sample_landmarks()
    baseline = normalize_landmarks(points, "Right")
    transformed = points * 2.5 + np.asarray((0.2, -0.1, 0.4), dtype=np.float32)
    candidate = normalize_landmarks(transformed, "Right")
    np.testing.assert_allclose(candidate, baseline, rtol=1e-5, atol=1e-5)


def test_normalization_aligns_palm_axis_upright():
    feature = normalize_landmarks(sample_landmarks(), "Right").reshape(21, 3)
    assert feature[9, 0] == pytest.approx(0.0, abs=1e-6)
    assert feature[9, 1] == pytest.approx(-1.0, abs=1e-6)


def test_left_hand_mirroring_canonicalizes_x_axis():
    right = sample_landmarks()
    left = right.copy()
    left[:, 0] = 2 * left[0, 0] - left[:, 0]
    right_feature = normalize_landmarks(right, "Right")
    left_feature = normalize_landmarks(left, "Left")
    np.testing.assert_allclose(left_feature, right_feature, rtol=1e-5, atol=1e-5)


def test_feature_distance_is_rms_distance():
    first = np.zeros(63, dtype=np.float32)
    second = np.ones(63, dtype=np.float32)
    assert feature_distance(first, second) == pytest.approx(1.0)
    assert math.isfinite(feature_distance(first, second))


@pytest.mark.parametrize("value", ["../escape", "contains space", "", "/absolute"])
def test_identifier_rejects_unsafe_values(value):
    with pytest.raises(ValueError):
        validate_identifier(value, "session_id")


def test_label_validation_is_case_insensitive():
    assert validate_label("auto_land") == "AUTO_LAND"
    with pytest.raises(ValueError):
        validate_label("SWIPE")


def test_capture_gate_requires_deliberate_recording():
    gate = CaptureGate(sample_hz=5.0, min_feature_delta=0.01)
    feature = np.zeros(63, dtype=np.float32)
    assert gate.evaluate(1.0, feature) == CaptureDecision.PAUSED
    gate.toggle_recording()
    assert gate.capture_block_index == 1
    assert gate.evaluate(1.0, feature) == CaptureDecision.ACCEPT


def test_capture_gate_starts_a_new_block_after_each_pause():
    gate = CaptureGate(sample_hz=5.0, min_feature_delta=0.01)
    assert gate.toggle_recording() is True
    assert gate.capture_block_index == 1
    assert gate.toggle_recording() is False
    assert gate.capture_block_index == 1
    assert gate.toggle_recording() is True
    assert gate.capture_block_index == 2


def test_capture_gate_locks_label_while_recording():
    gate = CaptureGate(sample_hz=5.0, min_feature_delta=0.01)
    assert gate.select_label("LEFT") is True
    gate.toggle_recording()
    assert gate.select_label("RIGHT") is False
    assert gate.label == "LEFT"


def test_capture_gate_rate_limits_and_rejects_near_duplicates():
    gate = CaptureGate(sample_hz=5.0, min_feature_delta=0.01)
    feature = np.zeros(63, dtype=np.float32)
    gate.toggle_recording()
    assert gate.evaluate(1.0, feature) == CaptureDecision.ACCEPT
    assert gate.evaluate(1.1, feature + 1.0) == CaptureDecision.RATE_LIMITED
    assert gate.evaluate(1.21, feature) == CaptureDecision.NEAR_DUPLICATE
    assert gate.evaluate(1.42, feature + 1.0) == CaptureDecision.ACCEPT


def test_capture_gate_no_hand_does_not_create_a_candidate():
    gate = CaptureGate(sample_hz=5.0, min_feature_delta=0.01)
    gate.toggle_recording()
    assert gate.evaluate(1.0, None) == CaptureDecision.NO_HAND
    assert gate.evaluate(1.0, np.zeros(63, dtype=np.float32)) == CaptureDecision.ACCEPT


def test_only_clean_quit_completes_session():
    assert final_session_status(True) == "COMPLETE"
    assert final_session_status(False) == "ABORTED"
