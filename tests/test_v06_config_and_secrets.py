from __future__ import annotations

from agent_os.config import (
    DEFAULT_AUTO_MODELS,
    DEFAULT_MODELS,
    Settings,
    configured_model_candidates,
    parse_model_ref,
)
from agent_os.secrets import SecretStore


def test_auto_model_candidates_preserve_order() -> None:
    settings = Settings(
        provider="auto",
        model="auto",
        auto_models="gemini:g1,openai:o1,gemini:g1,mistral:m1",
    )
    assert configured_model_candidates(settings) == [
        ("gemini", "g1"),
        ("openai", "o1"),
        ("mistral", "m1"),
    ]


def test_manual_model_is_first_candidate() -> None:
    settings = Settings(provider="openai", model="gpt-test", auto_switch_models=False)
    assert configured_model_candidates(settings) == [("openai", "gpt-test")]


def test_parse_model_ref_supports_default_provider() -> None:
    assert parse_model_ref("model-x", "mistral") == ("mistral", "model-x")
    assert parse_model_ref("gemini:model-y") == ("gemini", "model-y")


def test_secret_store_uses_environment_fallback(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "env-secret")
    store = SecretStore()
    monkeypatch.setattr(store, "_keyring", lambda: type("K", (), {"get_password": staticmethod(lambda *_: None)})())
    assert store.get("gemini") == "env-secret"
    assert store.source("gemini") == "GEMINI_API_KEY"


def test_legacy_agent_os_environment_is_not_promoted(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_OS_TARGET", "monitor:9")
    settings = Settings()
    assert settings.target != "monitor:9"


def test_current_default_routes_use_supported_model_ids() -> None:
    assert DEFAULT_AUTO_MODELS[:3] == (
        "gemini:gemini-3.5-flash-lite",
        "gemini:gemini-3.6-flash",
        "gemini:gemini-3.1-flash-lite",
    )
    assert DEFAULT_MODELS["mistral"] == "mistral-small-2603"
