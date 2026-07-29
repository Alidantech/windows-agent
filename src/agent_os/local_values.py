from __future__ import annotations

import threading

LOCAL_VALUE_TOKEN = "__WINDOWS_AGENT_SECRET__"


class LocalValueVault:
    """Keep a user-supplied sensitive value out of model prompts and logs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: str | None = None

    def set(self, value: str) -> None:
        candidate = value.strip()
        if not candidate:
            raise ValueError("A sensitive value cannot be empty.")
        with self._lock:
            self._value = candidate

    def get(self) -> str | None:
        with self._lock:
            return self._value

    def clear(self) -> None:
        with self._lock:
            self._value = None


local_value_vault = LocalValueVault()
