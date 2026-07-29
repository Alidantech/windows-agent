from __future__ import annotations

import os
from dataclasses import dataclass

SERVICE_NAME = "windows-agent"
PROVIDER_KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}


@dataclass(frozen=True)
class SecretStatus:
    provider: str
    configured: bool
    source: str | None = None


class SecretStore:
    """Store provider keys in the OS credential vault, with environment fallback."""

    def _keyring(self):
        try:
            import keyring
        except ImportError as exc:  # pragma: no cover - dependency is required in production
            raise RuntimeError("Install the keyring package to store API keys safely.") from exc
        return keyring

    @staticmethod
    def _normalize(provider: str) -> str:
        value = provider.strip().lower()
        if value not in PROVIDER_KEY_ENV:
            choices = ", ".join(sorted(PROVIDER_KEY_ENV))
            raise ValueError(f"Unknown provider {provider!r}. Available: {choices}.")
        return value

    def get(self, provider: str) -> str | None:
        name = self._normalize(provider)
        try:
            value = self._keyring().get_password(SERVICE_NAME, name)
        except Exception:
            value = None
        if value and value.strip():
            return value.strip()
        env_value = os.getenv(PROVIDER_KEY_ENV[name], "").strip()
        return env_value or None

    def source(self, provider: str) -> str | None:
        name = self._normalize(provider)
        try:
            if self._keyring().get_password(SERVICE_NAME, name):
                return "Windows Credential Manager"
        except Exception:
            pass
        if os.getenv(PROVIDER_KEY_ENV[name], "").strip():
            return PROVIDER_KEY_ENV[name]
        return None

    def set(self, provider: str, value: str) -> None:
        name = self._normalize(provider)
        secret = value.strip()
        if not secret:
            raise ValueError("API key cannot be empty.")
        self._keyring().set_password(SERVICE_NAME, name, secret)

    def delete(self, provider: str) -> None:
        name = self._normalize(provider)
        try:
            self._keyring().delete_password(SERVICE_NAME, name)
        except Exception:
            return

    def statuses(self) -> list[SecretStatus]:
        return [
            SecretStatus(provider=name, configured=self.get(name) is not None, source=self.source(name))
            for name in sorted(PROVIDER_KEY_ENV)
        ]


secret_store = SecretStore()
