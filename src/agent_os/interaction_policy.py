from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from agent_os.local_values import LOCAL_VALUE_TOKEN, local_value_vault
from agent_os.models import AgentDecision, UIElement

if TYPE_CHECKING:
    from agent_os.capture import CapturedObservation


InterventionMode = Literal["replace_text", "confirm_action", "manual"]


@dataclass(frozen=True)
class UserIntervention:
    question: str
    sensitive: bool = False
    guidance_label: str = "User answer"
    mode: InterventionMode = "manual"


class InteractionPolicy:
    """Require explicit user input for authored values, credentials, and consent."""

    _PASSWORD = re.compile(
        r"\b(?:password|passcode|security\s+answer|secret\s+answer|pin)\b",
        re.I,
    )
    _OTP = re.compile(
        r"\b(?:otp|one[- ]time|verification\s+code|security\s+code|"
        r"auth(?:entication)?\s+code|2fa|mfa)\b",
        re.I,
    )
    _HUMAN_CHECK = re.compile(
        r"\b(?:captcha|re-?captcha|hcaptcha|i\s+am\s+not\s+a\s+robot|"
        r"i'm\s+not\s+a\s+robot|human\s+verification)\b",
        re.I,
    )
    _PERSONAL_FIELDS: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\bfirst\s+name\b", re.I), "first name"),
        (re.compile(r"\blast\s+name\b", re.I), "last name"),
        (re.compile(r"\bfull\s+name\b|\byour\s+name\b", re.I), "full name"),
        (re.compile(r"\be-?mail(?:\s+address)?\b", re.I), "email address"),
        (re.compile(r"\b(?:phone|mobile|telephone)\b", re.I), "phone number"),
        (re.compile(r"\b(?:address|street|city|postal|zip)\b", re.I), "address"),
        (re.compile(r"\b(?:company|organisation|organization)\b", re.I), "company name"),
        (re.compile(r"\b(?:user\s*name|username)\b", re.I), "username"),
        (re.compile(r"\b(?:date\s+of\s+birth|birthday)\b", re.I), "date of birth"),
    )
    _CONSENT = re.compile(
        r"\b(?:terms(?:\s+and\s+conditions)?|privacy\s+policy|legal\s+agreement|"
        r"marketing\s+(?:emails?|messages?)|newsletter|consent|subscribe)\b",
        re.I,
    )
    _EXPLICIT_CONSENT = re.compile(
        r"\b(?:i\s+agree|agree\s+to|accept\s+the\s+terms|check\s+the\s+terms|"
        r"yes[, ]+i\s+agree|consent\s+to|subscribe\s+me)\b",
        re.I,
    )

    @staticmethod
    def _element(
        observation: CapturedObservation,
        element_id: str | None,
    ) -> UIElement | None:
        if not element_id:
            return None
        return next(
            (
                item
                for item in observation.uia.elements
                if item.element_id == element_id
            ),
            None,
        )

    @staticmethod
    def _element_label(element: UIElement | None) -> str:
        if element is None:
            return ""
        accessible = " ".join(
            part.strip()
            for part in (element.name, element.placeholder or "")
            if part and part.strip()
        )
        if accessible:
            return accessible
        return " ".join(
            part.strip()
            for part in (element.control_type, element.automation_id or "")
            if part and part.strip()
        )

    @staticmethod
    def _value_was_supplied(value: str, corpus: str) -> bool:
        candidate = value.strip()
        if candidate == LOCAL_VALUE_TOKEN:
            return False
        return bool(candidate) and (
            candidate in corpus or candidate.casefold() in corpus.casefold()
        )

    def required_intervention(
        self,
        decision: AgentDecision,
        observation: CapturedObservation,
        *,
        task: str,
        guidance: list[str],
    ) -> UserIntervention | None:
        element = self._element(observation, decision.element_id)
        element_name = self._element_label(element)
        corpus = "\n".join([task, *guidance])

        if self._HUMAN_CHECK.search(element_name):
            return UserIntervention(
                "Complete the CAPTCHA or human-verification step yourself in the assigned "
                "browser, then type 'done' here.",
                guidance_label="CAPTCHA completed by user",
                mode="manual",
            )

        if decision.action in {"fill_element", "type_text"} and decision.text is not None:
            label = element_name or "requested field"
            if (
                decision.text == LOCAL_VALUE_TOKEN
                and local_value_vault.matches_target(label)
            ):
                return None
            if self._PASSWORD.search(label) and not self._value_was_supplied(
                decision.text,
                corpus,
            ):
                return UserIntervention(
                    "Enter the password you want Windows Agent to use. "
                    "The answer will be masked.",
                    sensitive=True,
                    guidance_label="Password supplied by user",
                    mode="replace_text",
                )
            if self._OTP.search(label) and not self._value_was_supplied(
                decision.text,
                corpus,
            ):
                return UserIntervention(
                    "Enter the verification code shown or sent to you. "
                    "The answer will be masked.",
                    sensitive=True,
                    guidance_label="Verification code supplied by user",
                    mode="replace_text",
                )
            for pattern, friendly_name in self._PERSONAL_FIELDS:
                if pattern.search(label) and not self._value_was_supplied(
                    decision.text,
                    corpus,
                ):
                    return UserIntervention(
                        f"What {friendly_name} should I enter?",
                        sensitive=True,
                        guidance_label=f"{friendly_name.title()} supplied by user",
                        mode="replace_text",
                    )
            if (
                element is not None
                and element.editable
                and element.required
                and not element.has_value
                and not self._value_was_supplied(decision.text, corpus)
            ):
                clean_label = (element.name or element.placeholder or "required field").strip()
                return UserIntervention(
                    f"What value should I enter for required field '{clean_label}'?",
                    sensitive=True,
                    guidance_label=f"Value for {clean_label} supplied by user",
                    mode="replace_text",
                )

        if decision.action == "click_element" and element is not None:
            if self._CONSENT.search(element_name) and not self._EXPLICIT_CONSENT.search(
                corpus
            ):
                return UserIntervention(
                    "This control accepts terms, privacy, subscription, or other consent. "
                    "Type 'I agree' only after reviewing it, or type 'no' to stop.",
                    guidance_label="Consent decision supplied by user",
                    mode="confirm_action",
                )
        return None


def question_is_sensitive(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:password|passcode|pin|otp|verification\s+code|security\s+code|"
            r"authentication\s+code|2fa|mfa|api\s+key|secret|required\s+field)\b",
            question,
            re.I,
        )
    )
