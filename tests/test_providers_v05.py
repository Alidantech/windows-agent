from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from agent_os.cancellation import CancellationToken
from agent_os.config import DEFAULT_MODELS, Settings, load_settings, provider_api_key
from agent_os.models import AgentDecision, TaskVerification
from agent_os.providers.openai import OpenAIPlanner
from agent_os.providers.registry import (
    available_providers,
    create_planner,
    register_provider,
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    for name in (
        "WINDOWS_AGENT_PROVIDER",
        "WINDOWS_AGENT_MODEL",
        "WINDOWS_AGENT_TARGET",
        "AGENT_OS_PROVIDER",
        "AGENT_OS_MODEL",
        "AGENT_OS_TARGET",
        "GEMINI_MODEL",
        "OPENAI_MODEL",
        "MISTRAL_MODEL",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "MISTRAL_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_default_provider_and_model() -> None:
    settings = load_settings()
    assert settings.provider == "gemini"
    assert settings.model == DEFAULT_MODELS["gemini"]
    assert ".windows-agent" in str(settings.browser_profile_dir)


def test_legacy_agent_os_environment_is_promoted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_OS_TARGET", "monitor:2")
    monkeypatch.setenv("AGENT_OS_MODEL", "legacy-model")
    settings = load_settings()
    assert settings.target == "monitor:2"
    assert settings.model == "legacy-model"


def test_provider_specific_model_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WINDOWS_AGENT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    settings = load_settings()
    assert settings.provider == "openai"
    assert settings.model == "gpt-test"


def test_generic_model_has_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WINDOWS_AGENT_PROVIDER", "mistral")
    monkeypatch.setenv("WINDOWS_AGENT_MODEL", "generic-model")
    monkeypatch.setenv("MISTRAL_MODEL", "provider-model")
    settings = load_settings()
    assert settings.model == "generic-model"


def test_provider_api_key_uses_selected_provider_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret-openai")
    assert provider_api_key("openai") == "secret-openai"
    with pytest.raises(RuntimeError, match="MISTRAL_API_KEY"):
        provider_api_key("mistral")


def test_builtin_provider_registry() -> None:
    assert available_providers() == ("gemini", "mistral", "openai")


@dataclass
class FakePlanner:
    name: str = "fake"
    model: str = "fake-model"

    def plan(self, prompt: str, image_bytes: bytes) -> tuple[AgentDecision, str]:
        decision = AgentDecision(action="done", reason="fake")
        return decision, decision.model_dump_json()

    def verify(self, prompt: str, image_bytes: bytes) -> tuple[TaskVerification, str]:
        verification = TaskVerification(complete=True, confidence=1, evidence="fake")
        return verification, verification.model_dump_json()

    def close(self) -> None:
        return None


def test_custom_provider_registration() -> None:
    name = "test-custom-provider"

    def factory(settings, prompts, cancellation):
        return FakePlanner(model=settings.model)

    register_provider(name, factory, replace=True)
    settings = Settings(provider="gemini", model="custom-model")
    settings.provider = name  # Registry supports external names at runtime.
    planner = create_planner(settings, prompts=object(), cancellation=CancellationToken())
    assert planner.name == "fake"
    assert planner.model == "custom-model"


def test_openai_parsed_output_extraction() -> None:
    decision = AgentDecision(action="done", reason="complete")

    class Response:
        output_parsed = decision
        output_text = decision.model_dump_json()
        output = []

    parsed, raw = OpenAIPlanner._extract_parsed(Response(), AgentDecision)
    assert parsed == decision
    assert '"action":"done"' in raw
