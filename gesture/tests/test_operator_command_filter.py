import json
from pathlib import Path

from gesture.operator_command_filter import FilterConfig, GestureCommandFilter


REPO_ROOT = Path(__file__).resolve().parents[2]


def make_filter(**overrides):
    values = {
        "minimum_confidence": 0.8,
        "stable_frames": 3,
        "takeoff_stable_frames": 5,
        "minimum_transition_interval_sec": 0.2,
    }
    values.update(overrides)
    return GestureCommandFilter(FilterConfig(**values))


def test_no_hand_and_low_confidence_immediately_hold():
    command_filter = make_filter()
    for index in range(3):
        command_filter.update("FORWARD", 0.99, index * 0.1)
    assert command_filter.update(None, 0.0, 0.4).command == "HOLD"
    decision = command_filter.update("RIGHT", 0.79, 0.5)
    assert decision.command == "HOLD"
    assert decision.reason == "LOW_CONFIDENCE"
    assert not decision.valid


def test_direction_requires_stability_and_transition_never_replays_motion():
    command_filter = make_filter()
    assert command_filter.update("FORWARD", 0.9, 0.0).command == "HOLD"
    assert command_filter.update("FORWARD", 0.9, 0.1).command == "HOLD"
    assert command_filter.update("FORWARD", 0.9, 0.2).command == "FORWARD"
    assert command_filter.update("LEFT", 0.9, 0.3).command == "HOLD"
    assert command_filter.update("LEFT", 0.9, 0.4).command == "HOLD"
    assert command_filter.update("LEFT", 0.9, 0.5).command == "LEFT"


def test_takeoff_uses_stronger_dwell_and_explicit_hold_is_immediate():
    command_filter = make_filter()
    for index in range(4):
        assert command_filter.update("TAKEOFF", 0.95, index * 0.1).command == "HOLD"
    assert command_filter.update("TAKEOFF", 0.95, 0.4).command == "TAKEOFF"
    decision = command_filter.update("HOLD", 0.95, 0.5)
    assert decision.command == "HOLD"
    assert decision.valid


def test_checked_in_control_contract_is_conservative_and_complete():
    config = json.loads(
        (REPO_ROOT / "gesture/configs/uav_control_v1.json").read_text()
    )
    assert config["minimum_confidence"] >= 0.8
    assert config["takeoff_stable_frames"] > config["stable_frames"]
    assert 0.0 < config["command_ttl_sec"] <= 0.5
    assert config["manual_xy_speed_m_s"] == 0.5
    assert config["takeoff_altitude_m"] == 3.0
    assert config["auto_land_policy"].startswith("RECOGNIZE_AND_HOLD")
