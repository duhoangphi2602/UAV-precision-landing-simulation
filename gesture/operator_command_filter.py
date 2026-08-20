"""Conservative temporal filter for gesture operator commands."""

from __future__ import annotations

from dataclasses import dataclass

from gesture.onnx_runtime import NO_COMMAND


HOLD = "HOLD"
TAKEOFF = "TAKEOFF"
ACTIONABLE_COMMANDS = {
    TAKEOFF,
    "FORWARD",
    "BACKWARD",
    "LEFT",
    "RIGHT",
    "AUTO_LAND",
}
KNOWN_COMMANDS = ACTIONABLE_COMMANDS | {HOLD, NO_COMMAND}


@dataclass(frozen=True)
class FilterConfig:
    minimum_confidence: float
    stable_frames: int
    takeoff_stable_frames: int
    minimum_transition_interval_sec: float

    def validate(self) -> None:
        if not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between zero and one")
        if self.stable_frames <= 0:
            raise ValueError("stable_frames must be positive")
        if self.takeoff_stable_frames < self.stable_frames:
            raise ValueError("TAKEOFF dwell must be at least the normal dwell")
        if self.minimum_transition_interval_sec < 0.0:
            raise ValueError("minimum transition interval cannot be negative")


@dataclass(frozen=True)
class FilterDecision:
    command: str
    confidence: float
    valid: bool
    reason: str


class GestureCommandFilter:
    """Debounce movement while making every unsafe condition HOLD immediately."""

    def __init__(self, config: FilterConfig):
        config.validate()
        self.config = config
        self._candidate = NO_COMMAND
        self._candidate_frames = 0
        self._last_action_transition_sec = float("-inf")
        self._active_command = HOLD

    def _safe_hold(self, confidence: float, reason: str) -> FilterDecision:
        self._candidate = NO_COMMAND
        self._candidate_frames = 0
        self._active_command = HOLD
        return FilterDecision(HOLD, confidence, False, reason)

    def update(
        self,
        raw_command: str | None,
        confidence: float,
        now_sec: float,
    ) -> FilterDecision:
        command = NO_COMMAND if raw_command is None else raw_command.upper()
        if command not in KNOWN_COMMANDS:
            return self._safe_hold(confidence, "UNKNOWN_COMMAND")
        if command == NO_COMMAND:
            return self._safe_hold(confidence, "NO_HAND_OR_VETO")
        if confidence < self.config.minimum_confidence:
            return self._safe_hold(confidence, "LOW_CONFIDENCE")
        if command == HOLD:
            self._candidate = HOLD
            self._candidate_frames = 0
            self._active_command = HOLD
            return FilterDecision(HOLD, confidence, True, "EXPLICIT_HOLD")

        if command != self._candidate:
            self._candidate = command
            self._candidate_frames = 1
            self._active_command = HOLD
        else:
            self._candidate_frames += 1

        required = (
            self.config.takeoff_stable_frames
            if command == TAKEOFF
            else self.config.stable_frames
        )
        dwell_ready = self._candidate_frames >= required
        transition_ready = (
            now_sec - self._last_action_transition_sec
            >= self.config.minimum_transition_interval_sec
        )
        if dwell_ready and transition_ready:
            if self._active_command != command:
                self._last_action_transition_sec = now_sec
            self._active_command = command
            return FilterDecision(command, confidence, True, "STABLE")

        reason = "DEBOUNCE" if not dwell_ready else "TRANSITION_RATE_LIMIT"
        return FilterDecision(HOLD, confidence, False, reason)
