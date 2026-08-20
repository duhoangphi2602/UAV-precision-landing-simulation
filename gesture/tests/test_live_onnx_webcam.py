"""State-machine gates for the mandatory manual live smoke checklist."""

from gesture.live_onnx_webcam import LiveSmokeChecklist, SMOKE_GESTURES
from gesture.onnx_runtime import GesturePrediction, NO_COMMAND, no_hand_prediction
from gesture.thumb_veto import ALLOWED, REJECTED_BY_THUMB_VETO


def prediction(raw: str, effective: str, veto: str = ALLOWED) -> GesturePrediction:
    return GesturePrediction(raw, 0.99, 1.0, veto, effective, 0.01)


def test_checklist_requires_all_gestures_no_hand_transition_and_live_veto():
    checklist = LiveSmokeChecklist(required_consecutive=2)
    for label in SMOKE_GESTURES:
        for _ in range(2):
            checklist.update(True, prediction(label, label))
    for _ in range(2):
        checklist.update(False, no_hand_prediction())
    for label in ("HOLD", "FORWARD"):
        for _ in range(2):
            checklist.update(True, prediction(label, label))
    vetoed = prediction("AUTO_LAND", NO_COMMAND, REJECTED_BY_THUMB_VETO)
    for _ in range(2):
        checklist.update(True, vetoed)
    assert checklist.all_passed
    assert checklist.ambiguous_veto_activations == 2
    assert checklist.no_hand_command_violations == 0


def test_no_hand_violation_is_counted_and_cannot_satisfy_no_hand_task():
    checklist = LiveSmokeChecklist(required_consecutive=1)
    checklist.task_index = len(SMOKE_GESTURES)
    stale = prediction("TAKEOFF", "TAKEOFF")
    checklist.update(False, stale)
    assert checklist.no_hand_command_violations == 1
    assert checklist.current_task == "NO_HAND"
