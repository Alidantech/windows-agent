from __future__ import annotations

from dataclasses import dataclass

from agent_os.models import AgentDecision


@dataclass(frozen=True)
class SafetyAssessment:
    allowed: bool
    requires_confirmation: bool
    reason: str


class SafetyPolicy:
    """Small, explicit local policy. It does not replace human supervision."""

    BLOCKED_HOTKEYS = {
        frozenset({"ctrl", "alt", "delete"}),
        frozenset({"win", "l"}),
    }
    RISKY_HOTKEYS = {
        frozenset({"alt", "f4"}),
        frozenset({"shift", "delete"}),
        frozenset({"ctrl", "shift", "esc"}),
        frozenset({"win", "r"}),
    }

    def __init__(self, confirm_risky: bool) -> None:
        self.confirm_risky = confirm_risky

    def assess(self, decision: AgentDecision) -> SafetyAssessment:
        if decision.action == "hotkey":
            ordered_keys = [key.lower() for key in decision.keys or []]
            keys = frozenset("win" if key in {"windows", "winleft", "winright"} else key for key in ordered_keys)
            if keys in self.BLOCKED_HOTKEYS:
                return SafetyAssessment(False, False, f"Blocked hotkey: {'+'.join(ordered_keys)}")
            if keys in self.RISKY_HOTKEYS:
                return SafetyAssessment(
                    True,
                    self.confirm_risky,
                    f"Risky hotkey: {'+'.join(ordered_keys)}",
                )

        if decision.action == "press_key" and (decision.key or "").lower() == "delete":
            return SafetyAssessment(True, self.confirm_risky, "Delete key may remove selected content.")

        if decision.action == "type_text" and decision.text:
            lowered = decision.text.lower()
            sensitive_markers = ("password=", "api_key=", "secret=", "bearer ")
            if any(marker in lowered for marker in sensitive_markers):
                return SafetyAssessment(False, False, "Refusing to type text that resembles a secret.")

        return SafetyAssessment(True, False, "Allowed by local policy.")
