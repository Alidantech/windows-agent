from __future__ import annotations

import re
import threading

LOCAL_VALUE_TOKEN = "__WINDOWS_AGENT_SECRET__"


class LocalValueVault:
    """Keep one user-supplied form value out of model prompts and logs."""

    _STOPWORDS = {
        "what", "which", "should", "would", "could", "please", "enter", "use",
        "value", "required", "optional", "field", "input", "textbox", "box", "the",
        "a", "an", "for", "to", "i", "me", "you", "want", "windows", "agent",
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: str | None = None
        self._purpose: str = ""

    @staticmethod
    def _field_kind(text: str) -> str | None:
        value = " ".join(text.lower().split())
        patterns = (
            ("verification_code", r"\b(?:otp|verification code|security code|2fa|mfa)\b"),
            ("password", r"\b(?:password|passcode|pin|security answer)\b"),
            ("first_name", r"\bfirst name\b"),
            ("last_name", r"\blast name\b"),
            ("full_name", r"\b(?:full name|your name)\b"),
            ("email", r"\be-?mail(?: address)?\b"),
            ("phone", r"\b(?:phone|mobile|telephone)\b"),
            ("username", r"\b(?:username|user name)\b"),
            ("company", r"\b(?:company|organisation|organization)\b"),
            ("date_of_birth", r"\b(?:date of birth|birthday)\b"),
            ("address", r"\b(?:street|postal|zip|city|address)\b"),
        )
        for kind, pattern in patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return kind
        return None

    @classmethod
    def _tokens(cls, text: str) -> set[str]:
        quoted = re.search(r"['\"]([^'\"]{2,160})['\"]", text)
        candidate = quoted.group(1) if quoted else text
        words = set(re.findall(r"[a-z0-9]+", candidate.lower()))
        return {word for word in words if word not in cls._STOPWORDS and len(word) > 1}

    def set(self, value: str, *, purpose: str) -> None:
        if value == "":
            raise ValueError("A local form value cannot be empty.")
        with self._lock:
            self._value = value
            self._purpose = purpose

    def get(self) -> str | None:
        with self._lock:
            return self._value

    def matches_target(self, target: str) -> bool:
        with self._lock:
            if self._value is None:
                return False
            purpose = self._purpose
        expected = self._field_kind(purpose)
        actual = self._field_kind(target)
        if expected is not None or actual is not None:
            return expected is not None and expected == actual
        expected_tokens = self._tokens(purpose)
        actual_tokens = self._tokens(target)
        if not expected_tokens or not actual_tokens:
            return False
        return expected_tokens.issubset(actual_tokens) or (
            len(expected_tokens & actual_tokens) / len(expected_tokens) >= 0.75
        )

    def clear(self) -> None:
        with self._lock:
            self._value = None
            self._purpose = ""


local_value_vault = LocalValueVault()
