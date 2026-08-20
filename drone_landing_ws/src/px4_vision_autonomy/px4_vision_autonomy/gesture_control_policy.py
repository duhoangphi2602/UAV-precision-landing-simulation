"""Pure safety policy for Mission Commander's manual gesture-flight mode."""

from __future__ import annotations

import math
from dataclasses import dataclass


HOLD = "HOLD"
DIRECTION_COMMANDS = {"FORWARD", "BACKWARD", "LEFT", "RIGHT"}
KNOWN_COMMANDS = DIRECTION_COMMANDS | {"TAKEOFF", HOLD, "AUTO_LAND", "NO_COMMAND"}


@dataclass(frozen=True)
class OperatorInput:
    command: str
    confidence: float
    valid: bool
    stale: bool
    age_sec: float


@dataclass(frozen=True)
class SafeCommand:
    command: str
    reason: str


class TargetReadyGate:
    """Require distinct, current typed observations before a handoff."""

    def __init__(self, required_consecutive: int):
        if required_consecutive <= 0:
            raise ValueError("required target observations must be positive")
        self.required_consecutive = required_consecutive
        self.consecutive = 0
        self.last_sequence_id = None

    def observe(self, *, valid: bool, stale: bool, sequence_id: int) -> None:
        if not valid or stale:
            self.consecutive = 0
            self.last_sequence_id = sequence_id
            return
        if sequence_id == self.last_sequence_id:
            return
        self.last_sequence_id = sequence_id
        self.consecutive += 1

    def ready(self, *, observation_age_sec: float, maximum_age_sec: float) -> bool:
        return (
            self.consecutive >= self.required_consecutive
            and math.isfinite(observation_age_sec)
            and 0.0 <= observation_age_sec <= maximum_age_sec
        )


class ControlAuthorityLatch:
    """One-way HUMAN to AUTONOMOUS authority transition."""

    def __init__(self):
        self.manual_authority = True
        self.autonomous_landing_authority = False

    def authorize_auto_land(self, *, target_ready: bool) -> bool:
        if self.autonomous_landing_authority or not self.manual_authority:
            return False
        if not target_ready:
            return False
        self.manual_authority = False
        self.autonomous_landing_authority = True
        return True


def resolve_safe_command(
    operator_input: OperatorInput | None,
    *,
    ttl_sec: float,
    minimum_confidence: float,
    auto_land_enabled: bool = False,
) -> SafeCommand:
    """Resolve any absent, invalid, low-confidence, or stale input to HOLD."""

    if operator_input is None:
        return SafeCommand(HOLD, "NO_INPUT")
    if operator_input.command not in KNOWN_COMMANDS:
        return SafeCommand(HOLD, "UNKNOWN_COMMAND")
    if operator_input.stale or operator_input.age_sec > ttl_sec:
        return SafeCommand(HOLD, "STALE_COMMAND")
    if not operator_input.valid or operator_input.command == "NO_COMMAND":
        return SafeCommand(HOLD, "INVALID_OR_NO_HAND")
    if (
        not math.isfinite(operator_input.confidence)
        or operator_input.confidence < minimum_confidence
    ):
        return SafeCommand(HOLD, "LOW_CONFIDENCE")
    if operator_input.command == "AUTO_LAND":
        if auto_land_enabled:
            return SafeCommand("AUTO_LAND", "ACCEPTED")
        return SafeCommand(HOLD, "LANDING_HANDOFF_NOT_ENABLED")
    return SafeCommand(operator_input.command, "ACCEPTED")


def body_velocity_for_command(command: str, speed_m_s: float) -> tuple[float, float]:
    """Return MAVSDK body-frame (forward, right) velocity for one command."""

    if not math.isfinite(speed_m_s) or speed_m_s <= 0.0:
        raise ValueError("manual XY speed must be finite and positive")
    mapping = {
        "FORWARD": (speed_m_s, 0.0),
        "BACKWARD": (-speed_m_s, 0.0),
        "LEFT": (0.0, -speed_m_s),
        "RIGHT": (0.0, speed_m_s),
        HOLD: (0.0, 0.0),
        "TAKEOFF": (0.0, 0.0),
        "AUTO_LAND": (0.0, 0.0),
        "NO_COMMAND": (0.0, 0.0),
    }
    if command not in mapping:
        raise ValueError(f"unknown operator command: {command}")
    return mapping[command]
