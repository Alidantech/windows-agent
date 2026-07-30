from __future__ import annotations

from agent_os.confirmation_policy import ConfirmationMode, ConfirmationPolicy
from agent_os.interaction_policy import InteractionPolicy as BaseInteractionPolicy
from agent_os.interaction_policy import UserIntervention


class InteractionPolicy(BaseInteractionPolicy):
    """Combine protected-value prompts with single-use action-time confirmations."""

    def __init__(self) -> None:
        super().__init__()
        self.confirmations = ConfirmationPolicy()
        self._used_confirmation_entries: set[str] = set()

    def reset(self) -> None:
        self._used_confirmation_entries.clear()

    def _consume_prior_confirmation(
        self,
        risk_code: str,
        guidance: list[str],
    ) -> bool:
        prefix = f"Confirmed risk {risk_code}:"
        for entry in reversed(guidance):
            if not entry.startswith(prefix):
                continue
            if entry in self._used_confirmation_entries:
                return False
            self._used_confirmation_entries.add(entry)
            return True
        return False

    def required_intervention(
        self,
        decision,
        observation,
        *,
        task: str,
        guidance: list[str],
    ) -> UserIntervention | None:
        protected = super().required_intervention(
            decision,
            observation,
            task=task,
            guidance=guidance,
        )
        if protected is not None:
            return protected

        assessment = self.confirmations.assess(
            decision,
            observation,
            task=task,
            guidance=guidance,
        )
        if assessment.mode == ConfirmationMode.ALLOW:
            return None
        if assessment.mode == ConfirmationMode.DENY:
            return UserIntervention(
                f"Blocked by Windows Agent policy: {assessment.reason}",
                sensitive=assessment.sensitive,
                guidance_label=f"Blocked risk {assessment.risk_code}",
                mode="manual",
            )
        if assessment.mode == ConfirmationMode.HANDOFF:
            return UserIntervention(
                assessment.user_question or assessment.reason,
                sensitive=assessment.sensitive,
                guidance_label=f"User takeover for {assessment.risk_code}",
                mode="manual",
            )
        if self._consume_prior_confirmation(assessment.risk_code, guidance):
            return None
        return UserIntervention(
            assessment.user_question or assessment.reason,
            sensitive=assessment.sensitive,
            guidance_label=f"Confirmed risk {assessment.risk_code}",
            mode="confirm_action",
        )


__all__ = ["InteractionPolicy"]
