from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_os.cancellation import CancellationToken
from agent_os.config import Settings
from agent_os.models import AgentDecision, TaskVerification
from agent_os.providers import router as router_module
from agent_os.providers.router import RoutingPlanner


@dataclass
class FakeProvider:
    name: str
    model: str
    failure: Exception | None = None
    calls: list[tuple[str, bytes]] | None = None

    def plan(self, prompt: str, image_bytes: bytes):
        if self.calls is not None:
            self.calls.append((prompt, image_bytes))
        if self.failure:
            raise self.failure
        return AgentDecision(action="done", reason="complete"), "{}"

    def verify(self, prompt: str, image_bytes: bytes):
        if self.failure:
            raise self.failure
        return TaskVerification(complete=True, confidence=1, evidence="done"), "{}"

    def list_models(self):
        return []

    def close(self) -> None:
        return


class Prompts:
    system_instruction = "system"
    verifier_instruction = "verify"


def test_router_switches_on_rate_limit_with_same_context(monkeypatch) -> None:
    settings = Settings(
        provider="auto",
        auto_models="gemini:g1,openai:o1",
        api_retries=1,
        model_cooldown_seconds=5,
    )
    calls: list[tuple[str, bytes]] = []
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(router_module, "provider_ready", lambda _name: (True, "ready"))

    def create(_settings, _prompts, provider, model, _cancellation):
        if provider == "gemini":
            return FakeProvider(provider, model, RuntimeError("429 RESOURCE_EXHAUSTED"), calls)
        return FakeProvider(provider, model, None, calls)

    monkeypatch.setattr(router_module, "create_provider", create)
    planner = RoutingPlanner(settings, Prompts(), CancellationToken(), lambda e, d: events.append((e, d)))
    decision, _ = planner.plan("same prompt", b"same image")
    assert decision.action == "done"
    assert calls == [("same prompt", b"same image"), ("same prompt", b"same image")]
    fallback = next(data for event, data in events if event == "model_fallback")
    assert fallback["context_preserved"] is True


def test_router_does_not_switch_on_validation_failure(monkeypatch) -> None:
    settings = Settings(provider="auto", auto_models="gemini:g1,openai:o1", api_retries=1)
    monkeypatch.setattr(router_module, "provider_ready", lambda _name: (True, "ready"))
    created: list[str] = []

    def create(_settings, _prompts, provider, model, _cancellation):
        created.append(provider)
        return FakeProvider(provider, model, ValueError("bad structured response"))

    monkeypatch.setattr(router_module, "create_provider", create)
    planner = RoutingPlanner(settings, Prompts())
    with pytest.raises(ValueError, match="bad structured response"):
        planner.plan("prompt", b"image")
    assert created == ["gemini"]
