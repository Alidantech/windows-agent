from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from agent_os.cancellation import CancellationToken
from agent_os.config import Settings, configured_model_candidates
from agent_os.models import AgentDecision, TaskVerification
from agent_os.prompts import PromptBuilder
from agent_os.providers.base import PlannerProvider
from agent_os.providers.registry import create_provider, provider_ready

EventSink = Callable[[str, dict[str, object]], None]


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


class RoutingPlanner:
    """Route the same prompt/context across models without losing run history."""

    name = "auto"

    def __init__(self, settings: Settings, prompts: PromptBuilder, cancellation: CancellationToken | None = None, event_sink: EventSink | None = None) -> None:
        self.settings = settings
        self.prompts = prompts
        self.cancellation = cancellation or CancellationToken()
        self.event_sink = event_sink or (lambda _event, _data: None)
        self.routes = [ModelRoute(*item) for item in configured_model_candidates(settings)]
        self._cooldown_until: dict[str, float] = {}
        self._current: ModelRoute | None = None
        self._provider: PlannerProvider | None = None
        self._switches = 0

    @property
    def model(self) -> str:
        return self._current.model if self._current else "auto"

    @property
    def current_label(self) -> str:
        return self._current.label if self._current else "auto"

    @staticmethod
    def _retryable(exc: BaseException) -> bool:
        text = f"{type(exc).__name__}: {exc}".lower()
        markers = (
            "429", "resource_exhausted", "rate limit", "ratelimit", "quota", "too many requests",
            "503", "unavailable", "overloaded", "timeout", "timed out", "connection", "getaddrinfo",
            "temporarily", "server error", "502", "504",
        )
        return any(marker in text for marker in markers)

    @staticmethod
    def _retry_after(exc: BaseException) -> int | None:
        text = str(exc)
        match = re.search(r"retry(?:Delay| in)?[^0-9]{0,20}(\d+)(?:\.\d+)?\s*s", text, re.I)
        return int(match.group(1)) if match else None

    def _cooldown_seconds(self, exc: BaseException) -> int:
        text = str(exc).lower()
        retry_after = self._retry_after(exc) or 0
        if any(marker in text for marker in (
            "perday", "requestsperday", "tokensperday", "daily quota", " rpd",
        )):
            return max(12 * 60 * 60, retry_after)
        return max(self.settings.model_cooldown_seconds, retry_after)

    def _select_routes(self) -> list[ModelRoute]:
        now = time.monotonic()
        ready: list[ModelRoute] = []
        for route in self.routes:
            ok, reason = provider_ready(route.provider)
            if not ok:
                self.event_sink("model_skipped", {"route": route.label, "reason": reason})
                continue
            if self._cooldown_until.get(route.label, 0) > now:
                continue
            ready.append(route)
        return ready

    def _activate(self, route: ModelRoute) -> PlannerProvider:
        if self._current == route and self._provider is not None:
            return self._provider
        if self._provider is not None:
            self._provider.close()
        self._current = route
        self._provider = create_provider(self.settings, self.prompts, route.provider, route.model, self.cancellation)
        self.event_sink("model_selected", {"provider": route.provider, "model": route.model, "route": route.label})
        return self._provider

    def _call(self, method: str, prompt: str, image_bytes: bytes):
        routes = self._select_routes()
        if not routes:
            raise RuntimeError("No configured AI model is ready. Use /models and /key status.")
        if self._current in routes:
            routes.remove(self._current)
            routes.insert(0, self._current)
        errors: list[str] = []
        switches = 0
        for index, route in enumerate(routes):
            if index > 0:
                switches += 1
                if switches > self.settings.max_provider_switches:
                    break
            provider = self._activate(route)
            try:
                return getattr(provider, method)(prompt, image_bytes)
            except BaseException as exc:
                errors.append(f"{route.label}: {exc}")
                if not self.settings.auto_switch_models or not self._retryable(exc):
                    raise
                cooldown = self._cooldown_seconds(exc)
                self._cooldown_until[route.label] = time.monotonic() + cooldown
                self.event_sink("model_fallback", {
                    "from": route.label,
                    "reason": str(exc)[:500],
                    "cooldown_seconds": cooldown,
                    "context_preserved": True,
                })
        raise RuntimeError("All configured models failed: " + " | ".join(errors))

    def plan(self, prompt: str, image_bytes: bytes) -> tuple[AgentDecision, str]:
        return self._call("plan", prompt, image_bytes)

    def verify(self, prompt: str, image_bytes: bytes) -> tuple[TaskVerification, str]:
        return self._call("verify", prompt, image_bytes)

    def close(self) -> None:
        if self._provider is not None:
            self._provider.close()
        self._provider = None
