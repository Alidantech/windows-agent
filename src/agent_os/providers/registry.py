from __future__ import annotations

from collections.abc import Callable

from agent_os.cancellation import CancellationToken
from agent_os.config import Settings
from agent_os.prompts import PromptBuilder
from agent_os.providers.base import PlannerProvider

ProviderFactory = Callable[[Settings, PromptBuilder, CancellationToken | None], PlannerProvider]


def _gemini_factory(
    settings: Settings,
    prompts: PromptBuilder,
    cancellation: CancellationToken | None,
) -> PlannerProvider:
    from agent_os.providers.gemini import GeminiPlanner

    return GeminiPlanner(settings, prompts, cancellation)


def _openai_factory(
    settings: Settings,
    prompts: PromptBuilder,
    cancellation: CancellationToken | None,
) -> PlannerProvider:
    from agent_os.providers.openai import OpenAIPlanner

    return OpenAIPlanner(settings, prompts, cancellation)


def _mistral_factory(
    settings: Settings,
    prompts: PromptBuilder,
    cancellation: CancellationToken | None,
) -> PlannerProvider:
    from agent_os.providers.mistral import MistralPlanner

    return MistralPlanner(settings, prompts, cancellation)


_FACTORIES: dict[str, ProviderFactory] = {
    "gemini": _gemini_factory,
    "openai": _openai_factory,
    "mistral": _mistral_factory,
}


def available_providers() -> tuple[str, ...]:
    return tuple(sorted(_FACTORIES))


def register_provider(name: str, factory: ProviderFactory, *, replace: bool = False) -> None:
    normalized = name.strip().lower()
    if not normalized:
        raise ValueError("Provider name cannot be empty.")
    if normalized in _FACTORIES and not replace:
        raise ValueError(f"Provider {normalized!r} is already registered.")
    _FACTORIES[normalized] = factory


def create_planner(
    settings: Settings,
    prompts: PromptBuilder,
    cancellation: CancellationToken | None = None,
) -> PlannerProvider:
    provider = settings.provider.strip().lower()
    factory = _FACTORIES.get(provider)
    if factory is None:
        choices = ", ".join(available_providers())
        raise RuntimeError(f"Unknown AI provider {provider!r}. Available providers: {choices}.")
    return factory(settings, prompts, cancellation)
