import math

import pytest

from px4_vision_autonomy.gesture_control_policy import (
    ControlAuthorityLatch,
    OperatorInput,
    TargetReadyGate,
    body_velocity_for_command,
    resolve_safe_command,
)


def operator_input(command="FORWARD", **overrides):
    values = {
        "command": command,
        "confidence": 0.95,
        "valid": True,
        "stale": False,
        "age_sec": 0.1,
    }
    values.update(overrides)
    return OperatorInput(**values)


@pytest.mark.parametrize(
    "value,reason",
    [
        (None, "NO_INPUT"),
        (operator_input(valid=False), "INVALID_OR_NO_HAND"),
        (operator_input(command="NO_COMMAND"), "INVALID_OR_NO_HAND"),
        (operator_input(stale=True), "STALE_COMMAND"),
        (operator_input(age_sec=0.51), "STALE_COMMAND"),
        (operator_input(confidence=0.79), "LOW_CONFIDENCE"),
        (operator_input(confidence=math.nan), "LOW_CONFIDENCE"),
    ],
)
def test_unsafe_operator_input_resolves_to_hold(value, reason):
    decision = resolve_safe_command(value, ttl_sec=0.5, minimum_confidence=0.8)
    assert decision.command == "HOLD"
    assert decision.reason == reason


def test_auto_land_is_recognized_but_cannot_take_authority():
    decision = resolve_safe_command(
        operator_input(command="AUTO_LAND"),
        ttl_sec=0.5,
        minimum_confidence=0.8,
    )
    assert decision.command == "HOLD"
    assert decision.reason == "LANDING_HANDOFF_NOT_ENABLED"


def test_auto_land_can_only_pass_when_the_final_mode_explicitly_enables_it():
    decision = resolve_safe_command(
        operator_input(command="AUTO_LAND"),
        ttl_sec=0.5,
        minimum_confidence=0.8,
        auto_land_enabled=True,
    )
    assert decision.command == "AUTO_LAND"
    assert decision.reason == "ACCEPTED"


def test_target_ready_requires_distinct_current_valid_observations():
    gate = TargetReadyGate(required_consecutive=3)
    gate.observe(valid=True, stale=False, sequence_id=10)
    gate.observe(valid=True, stale=False, sequence_id=10)
    assert not gate.ready(observation_age_sec=0.1, maximum_age_sec=0.5)
    gate.observe(valid=True, stale=False, sequence_id=11)
    gate.observe(valid=True, stale=False, sequence_id=12)
    assert gate.ready(observation_age_sec=0.5, maximum_age_sec=0.5)
    assert not gate.ready(observation_age_sec=0.51, maximum_age_sec=0.5)
    gate.observe(valid=False, stale=True, sequence_id=13)
    assert not gate.ready(observation_age_sec=0.0, maximum_age_sec=0.5)


def test_authority_handoff_is_target_gated_and_permanently_one_way():
    latch = ControlAuthorityLatch()
    assert not latch.authorize_auto_land(target_ready=False)
    assert latch.manual_authority
    assert not latch.autonomous_landing_authority
    assert latch.authorize_auto_land(target_ready=True)
    assert not latch.manual_authority
    assert latch.autonomous_landing_authority
    assert not latch.authorize_auto_land(target_ready=True)


def test_manual_body_axis_sign_contract():
    assert body_velocity_for_command("FORWARD", 0.5) == (0.5, 0.0)
    assert body_velocity_for_command("BACKWARD", 0.5) == (-0.5, 0.0)
    assert body_velocity_for_command("LEFT", 0.5) == (0.0, -0.5)
    assert body_velocity_for_command("RIGHT", 0.5) == (0.0, 0.5)
    assert body_velocity_for_command("HOLD", 0.5) == (0.0, 0.0)
