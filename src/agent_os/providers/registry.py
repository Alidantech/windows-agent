from __future__ import annotations

import importlib.util
from collections.abc import Callable

from agent_os.cancellation import CancellationToken
from agent_os.config import Settings
from agent_os.prompts import PromptBuilder
from agent_os.providers.base import PlannerProvider
from agent_os.secrets import secret_store

ProviderFactory = Callable[[Settings, PromptBuilder, str, CancellationToken | None], PlannerProvider]


def _gemini(settings: Settings, prompts: PromptBuilder, model: str, cancellation: CancellationToken | None) -> PlannerProvider:
    from agent_os.providers.gemini import GeminiPlanner
    return GeminiPlanner(settings, prompts, model, cancellation)


def _openai(settings: Settings, prompts: PromptBuilder, model: str, cancellation: CancellationToken | None) -> PlannerProvider:
    from agent_os.providers.openai import OpenAIPlanner
    return OpenAIPlanner(settings, prompts, model, cancellation)


def _mistral(settings: Settings, prompts: PromptBuilder, model: str, cancellation: CancellationToken | None) -> PlannerProvider:
    from agent_os.providers.mistral import MistralPlanner
    return MistralPlanner(settings, prompts, model, cancellation)


_FACTORIES: dict[str, ProviderFactory] = {"gemini": _gemini, "openai": _openai, "mistral": _mistral}
_SDK_MODULES = {"gemini": "google.genai", "openai": "openai", "mistral": "mistralai"}


def available_providers() -> tuple[str, ...]:
    return tuple(sorted(_FACTORIES))


def provider_ready(name: str) -> tuple[bool, str]:
    normalized = name.strip().lower()
    if normalized not in _FACTORIES:
        return False, "unknown provider"
    if secret_store.get(normalized) is None:
        return False, "API key missing"
    try:
        sdk_found = importlib.util.find_spec(_SDK_MODULES[normalized]) is not None
    except (ImportError, ModuleNotFoundError):
        sdk_found = False
    if not sdk_found:
        return False, f"SDK missing ({_SDK_MODULES[normalized]})"
    return True, "ready"


def create_provider(settings: Settings, prompts: PromptBuilder, provider: str, model: str, cancellation: CancellationToken | None = None) -> PlannerProvider:
    normalized = provider.strip().lower()
    factory = _FACTORIES.get(normalized)
    if factory is None:
        raise RuntimeError(f"Unknown provider {provider!r}.")
    return factory(settings, prompts, model, cancellation)
