from __future__ import annotations

import threading


class AgentCancelled(KeyboardInterrupt):
    """Raised when the current Windows Agent task is cancelled by the user."""


class CancellationToken:
    """Thread-safe cooperative cancellation shared by providers and tools."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._reason = "Task cancelled."

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str:
        return self._reason

    def reset(self) -> None:
        self._reason = "Task cancelled."
        self._event.clear()

    def cancel(self, reason: str = "Task cancelled by user.") -> None:
        self._reason = reason
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise AgentCancelled(self.reason)

    def wait(self, seconds: float) -> bool:
        """Wait, returning True when cancellation occurs before the timeout."""
        return self._event.wait(max(0.0, seconds))
