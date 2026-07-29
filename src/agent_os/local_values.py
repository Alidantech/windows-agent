from __future__ import annotations

import re
import threading

LOCAL_VALUE_TOKEN = "__WINDOWS_AGENT_SECRET__"


class LocalValueVault:
    """Keep one user-supplied value out of model prompts and logs."""

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
            expected = self._field_kind(self._purpose)
        actual = self._field_kind(target)
        return expected is not None and expected == actual

    def clear(self) -> None:
        with self._lock:
            self._value = None
            self._purpose = ""


local_value_vault = LocalValueVault()
