"""Backward-compatible provider facade.

New integrations should import from :mod:`agent_os.providers`. The historical
``GeminiPlanner`` constructor is retained as a provider-neutral factory so the
v0.4 agent core can select Gemini, OpenAI, or Mistral without a hard break.
"""

from __future__ import annotations

from agent_os.cancellation import CancellationToken
from agent_os.config import Settings
from agent_os.prompts import PromptBuilder
from agent_os.providers import (
    PlannerProvider,
    available_providers,
    create_planner,
    register_provider,
)


class GeminiPlanner:
    """Compatibility constructor that returns the configured provider adapter."""

    def __new__(
        cls,
        settings: Settings,
        prompts: PromptBuilder,
        cancellation: CancellationToken | None = None,
    ) -> PlannerProvider:
        return create_planner(settings, prompts, cancellation)


__all__ = [
    "GeminiPlanner",
    "PlannerProvider",
    "available_providers",
    "create_planner",
    "register_provider",
]
