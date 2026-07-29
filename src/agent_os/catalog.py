from __future__ import annotations

from agent_os.config import DEFAULT_AUTO_MODELS, DEFAULT_MODELS, Settings, parse_model_ref
from agent_os.prompts import PromptBuilder
from agent_os.providers.base import ModelInfo
from agent_os.providers.registry import create_provider, provider_ready


def recommended_models() -> list[ModelInfo]:
    seen: set[tuple[str, str]] = set()
    output: list[ModelInfo] = []
    for ref in DEFAULT_AUTO_MODELS:
        provider, model = parse_model_ref(ref)
        if (provider, model) not in seen:
            output.append(ModelInfo(provider, model, available=False, vision=True, details="recommended"))
            seen.add((provider, model))
    for provider, model in DEFAULT_MODELS.items():
        if (provider, model) not in seen:
            output.append(ModelInfo(provider, model, available=False, vision=True, details="default"))
    return output


def list_models(settings: Settings, prompts: PromptBuilder, provider: str | None = None) -> tuple[list[ModelInfo], list[str]]:
    providers = [provider] if provider else ["gemini", "openai", "mistral"]
    results: list[ModelInfo] = []
    errors: list[str] = []
    for name in providers:
        if name is None:
            continue
        ready, reason = provider_ready(name)
        if not ready:
            errors.append(f"{name}: {reason}")
            continue
        model = DEFAULT_MODELS[name]
        adapter = create_provider(settings, prompts, name, model)
        try:
            results.extend(adapter.list_models())
        except Exception as exc:
            errors.append(f"{name}: {exc}")
        finally:
            adapter.close()
    if not results:
        results = recommended_models()
    return results, errors
