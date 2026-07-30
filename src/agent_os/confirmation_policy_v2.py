from __future__ import annotations

import re

from agent_os.confirmation_policy import ConfirmationPolicy as BaseConfirmationPolicy


class ConfirmationPolicy(BaseConfirmationPolicy):
    """Production refinements that classify the control, not model-authored rationale text."""

    _ACCOUNT_FINAL = re.compile(
        r"\b(?:create\s+(?:my\s+)?account|sign\s*up|register\s+(?:my\s+)?account|"
        r"finish\s+(?:account\s+)?registration|confirm\s+account)\b",
        re.I,
    )
    _PERMISSION = re.compile(
        r"\b(?:camera|microphone|precise\s+location|location\s+permission|"
        r"browser\s+permission|windows\s+permission|notification\s+permission|"
        r"grant\s+permission)\b",
        re.I,
    )

    @classmethod
    def _label(cls, decision, observation) -> str:
        element = cls._element(observation, decision.element_id)
        parts = [
            element.name if element else "",
            element.placeholder if element and element.placeholder else "",
            element.control_type if element else "",
            decision.option or "",
            decision.url or "",
            decision.app or "",
            decision.window or "",
        ]
        return " ".join(part.strip() for part in parts if part and part.strip())


__all__ = ["ConfirmationPolicy"]
