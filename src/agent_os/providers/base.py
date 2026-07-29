from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from agent_os.cancellation import CancellationToken
from agent_os.config import Settings
from agent_os.models import AgentDecision, TaskVerification

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")


@runtime_checkable
class PlannerProvider(Protocol):
    """Common planner contract implemented by every model provider."""

    name: str
    model: str

    def plan(self, prompt: str, image_bytes: bytes) -> tuple[AgentDecision, str]: ...

    def verify(self, prompt: str, image_bytes: bytes) -> tuple[TaskVerification, str]: ...

    def close(self) -> None: ...


class CancellableProvider:
    """Shared retry and Ctrl+C behavior for synchronous provider SDKs."""

    name = "provider"

    def __init__(self, settings: Settings, cancellation: CancellationToken | None = None) -> None:
        self.settings = settings
        self.model = settings.model
        self.cancellation = cancellation or CancellationToken()

    def _run_once(self, operation: Callable[[], R]) -> R:
        output: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

        def worker() -> None:
            try:
                output.put(("ok", operation()))
            except Exception as exc:
                output.put(("error", exc))

        threading.Thread(
            target=worker,
            name=f"windows-agent-{self.name}-request",
            daemon=True,
        ).start()

        while True:
            self.cancellation.raise_if_cancelled()
            try:
                kind, value = output.get(timeout=0.1)
            except queue.Empty:
                continue
            if kind == "error":
                assert isinstance(value, Exception)
                raise value
            return value  # type: ignore[return-value]

    def _with_retries(self, operation: Callable[[], R]) -> R:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.api_retries + 1):
            self.cancellation.raise_if_cancelled()
            try:
                return self._run_once(operation)
            except Exception as exc:
                last_error = exc
                if attempt < self.settings.api_retries:
                    delay = self.settings.api_retry_base_seconds * (2 ** (attempt - 1))
                    if self.cancellation.wait(delay):
                        self.cancellation.raise_if_cancelled()
        raise RuntimeError(
            f"{self.name.title()} request failed after "
            f"{self.settings.api_retries} attempts: {last_error}"
        ) from last_error

    def close(self) -> None:
        """Providers may override this when their SDK owns persistent resources."""
