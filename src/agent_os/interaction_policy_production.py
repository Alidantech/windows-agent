from __future__ import annotations

from agent_os.confirmation_policy import ConfirmationMode, ConfirmationPolicy
from agent_os.interaction_policy import InteractionPolicy as BaseInteractionPolicy
from agent_os.interaction_policy import UserIntervention


class InteractionPolicy(BaseInteractionPolicy):
    """Combine protected-value prompts with action-time side-effect confirmations."""

    def __init__(self) -> None:
        super().__init__()
        self.confirmations = ConfirmationPolicy()

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
        return UserIntervention(
            assessment.user_question or assessment.reason,
            sensitive=assessment.sensitive,
            guidance_label=f"Confirmed risk {assessment.risk_code}",
            mode="confirm_action",
        )


__all__ = ["InteractionPolicy"]
