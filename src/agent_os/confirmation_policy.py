from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from agent_os.content_trust import action_may_transmit

if TYPE_CHECKING:
    from agent_os.capture import CapturedObservation
    from agent_os.models import AgentDecision, UIElement


class ConfirmationMode(StrEnum):
    ALLOW = "allow"
    PREAPPROVAL = "preapproval"
    ALWAYS_CONFIRM = "always_confirm"
    HANDOFF = "handoff"
    DENY = "deny"


@dataclass(frozen=True)
class ConfirmationAssessment:
    mode: ConfirmationMode
    risk_code: str
    reason: str
    user_question: str | None = None
    sensitive: bool = False

    @property
    def allowed_without_confirmation(self) -> bool:
        return self.mode == ConfirmationMode.ALLOW


class ConfirmationPolicy:
    """Risk-based UI policy kept separate from the model's autonomy grant."""

    _DELETE = re.compile(
        r"\b(?:delete|remove|erase|trash|cancel\s+(?:appointment|reservation|booking|order)|"
        r"close\s+account|terminate\s+account)\b",
        re.I,
    )
    _ACCOUNT_FINAL = re.compile(
        r"\b(?:create\s+(?:my\s+)?account|sign\s*up|register|finish\s+registration|"
        r"confirm\s+account)\b",
        re.I,
    )
    _PERSISTENT_ACCESS = re.compile(
        r"\b(?:create|generate|issue|save)\b.{0,50}\b(?:api|oauth|access)\s*(?:key|token)|"
        r"\bsave\b.{0,40}\b(?:password|credit\s+card)\b",
        re.I | re.S,
    )
    _COMMUNICATION = re.compile(
        r"\b(?:send|post|publish|comment|reply|message|submit|apply|book|reserve|schedule|"
        r"like|react|review|invite)\b",
        re.I,
    )
    _SUBSCRIBE = re.compile(r"\b(?:subscribe|unsubscribe|newsletter|notifications?|sms)\b", re.I)
    _FINANCIAL = re.compile(
        r"\b(?:pay|purchase|buy|checkout|place\s+order|confirm\s+payment|transfer|"
        r"schedule\s+payment|subscription)\b",
        re.I,
    )
    _INSTALL = re.compile(
        r"\b(?:install|run\s+downloaded|launch\s+downloaded|browser\s+extension|add\s+extension)\b",
        re.I,
    )
    _UPLOAD = re.compile(r"\b(?:upload|attach|choose\s+file|select\s+file)\b", re.I)
    _LOGIN = re.compile(r"\b(?:log\s*in|sign\s*in|continue\s+with|authenticate)\b", re.I)
    _PERMISSION = re.compile(
        r"\b(?:allow|grant|permission|camera|microphone|location|notifications?)\b",
        re.I,
    )
    _CONSENT = re.compile(
        r"\b(?:terms|privacy\s+policy|legal\s+agreement|i\s+agree|accept)\b",
        re.I,
    )
    _CAPTCHA = re.compile(
        r"\b(?:captcha|re-?captcha|hcaptcha|not\s+a\s+robot|human\s+verification)\b",
        re.I,
    )
    _PASSWORD_CHANGE = re.compile(
        r"\b(?:change|reset|update)\b.{0,50}\b(?:password|passcode|pin)\b",
        re.I | re.S,
    )
    _SECURITY_BARRIER = re.compile(
        r"\b(?:site\s+not\s+secure|certificate\s+warning|continue\s+unsafe|bypass|paywall)\b",
        re.I,
    )
    _SECURITY_SETTINGS = re.compile(
        r"\b(?:windows\s+security|defender|antivirus|firewall|privacy\s+settings|"
        r"security\s+settings|vpn|password\s+manager)\b",
        re.I,
    )
    _MEDICAL = re.compile(
        r"\b(?:prescribe|diagnose|patient\s+note|medical\s+record|appointment\s+for\s+care|"
        r"treatment|medication)\b",
        re.I,
    )
    _SENSITIVE_FIELD = re.compile(
        r"\b(?:password|passcode|pin|otp|verification\s+code|api\s*key|token|secret|"
        r"email|phone|address|passport|ssn|national\s+id|medical|financial|bank|card)\b",
        re.I,
    )

    @staticmethod
    def _element(observation: CapturedObservation, element_id: str | None) -> UIElement | None:
        if not element_id:
            return None
        return next(
            (item for item in observation.uia.elements if item.element_id == element_id),
            None,
        )

    @classmethod
    def _label(cls, decision: AgentDecision, observation: CapturedObservation) -> str:
        element = cls._element(observation, decision.element_id)
        parts = [
            element.name if element else "",
            element.placeholder if element and element.placeholder else "",
            element.control_type if element else "",
            decision.option or "",
            decision.text or "",
            decision.message or "",
            decision.url or "",
            decision.reason or "",
        ]
        return " ".join(part.strip() for part in parts if part and part.strip())

    @staticmethod
    def _explicit(task: str, pattern: re.Pattern[str]) -> bool:
        return bool(pattern.search(task))

    @staticmethod
    def _url_domain(url: str | None) -> str | None:
        if not url:
            return None
        normalized = url if "://" in url else f"https://{url}"
        return urlparse(normalized).hostname

    def assess(
        self,
        decision: AgentDecision,
        observation: CapturedObservation,
        *,
        task: str,
        guidance: list[str] | tuple[str, ...] = (),
    ) -> ConfirmationAssessment:
        label = self._label(decision, observation)
        user_corpus = "\n".join([task, *guidance])
        trust = observation.state.get("content_trust")
        injection_flagged = bool(trust.get("flagged")) if isinstance(trust, dict) else False

        if self._SECURITY_SETTINGS.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.DENY,
                "SECURITY_OR_PRIVACY_SETTINGS",
                "Windows Agent does not automate security, privacy, anti-malware, VPN, or password-manager settings.",
            )
        if self._PASSWORD_CHANGE.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.HANDOFF,
                "PASSWORD_CHANGE_FINAL_STEP",
                "The user must personally complete the final password-change submission.",
                "Take over the target window and complete the final password-change step, then tell me when it is done.",
                sensitive=True,
            )
        if self._SECURITY_BARRIER.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.HANDOFF,
                "SECURITY_BARRIER_BYPASS",
                "Windows Agent will not bypass browser or Windows safety barriers.",
                "Take over if you intend to handle this warning yourself; Windows Agent will not bypass it.",
            )
        if self._CAPTCHA.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.HANDOFF,
                "HUMAN_VERIFICATION",
                "CAPTCHA and human-verification controls require user takeover.",
                "Complete the CAPTCHA or human-verification step yourself, then type 'done'.",
            )

        if self._DELETE.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.ALWAYS_CONFIRM,
                "DELETE_DATA",
                "This action may delete or cancel data.",
                f"Confirm immediately before I perform this delete/cancel action: {label[:180]}",
            )
        if self._PERSISTENT_ACCESS.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.ALWAYS_CONFIRM,
                "PERSISTENT_ACCESS",
                "This action creates or stores persistent access credentials.",
                f"Confirm immediately before I create or save persistent access: {label[:180]}",
                sensitive=True,
            )
        if self._ACCOUNT_FINAL.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.ALWAYS_CONFIRM,
                "ACCOUNT_CREATION_FINAL_STEP",
                "This appears to be the final step of account creation.",
                f"Confirm immediately before I create the account: {label[:180]}",
            )
        if self._INSTALL.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.ALWAYS_CONFIRM,
                "INSTALL_OR_RUN_NEW_SOFTWARE",
                "Installing or running newly acquired software requires action-time confirmation.",
                f"Confirm immediately before I install or run this software: {label[:180]}",
            )
        if self._FINANCIAL.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.ALWAYS_CONFIRM,
                "FINANCIAL_TRANSACTION",
                "This action may confirm a purchase, payment, or subscription.",
                f"Confirm immediately before I perform this financial action: {label[:180]}",
                sensitive=True,
            )
        if self._MEDICAL.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.ALWAYS_CONFIRM,
                "MEDICAL_CARE_ACTION",
                "A medical-care action requires immediate user confirmation.",
                f"Confirm immediately before I perform this medical action: {label[:180]}",
                sensitive=True,
            )
        if self._SUBSCRIBE.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.ALWAYS_CONFIRM,
                "SUBSCRIPTION_OR_NOTIFICATION",
                "Subscribing or unsubscribing communications requires confirmation.",
                f"Confirm immediately before I change this subscription: {label[:180]}",
            )
        if self._COMMUNICATION.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.ALWAYS_CONFIRM,
                "REPRESENTATIONAL_COMMUNICATION",
                "This action may submit, send, post, publish, book, apply, or otherwise represent the user to a third party.",
                f"Confirm immediately before I perform this external action: {label[:180]}",
            )
        if self._CONSENT.search(label):
            return ConfirmationAssessment(
                ConfirmationMode.ALWAYS_CONFIRM,
                "LEGAL_OR_MARKETING_CONSENT",
                "This action accepts legal terms, privacy terms, or marketing consent.",
                f"Confirm immediately before I accept this consent: {label[:180]}",
            )

        if self._UPLOAD.search(label):
            if self._explicit(user_corpus, self._UPLOAD):
                return ConfirmationAssessment(
                    ConfirmationMode.ALLOW,
                    "UPLOAD_PREAPPROVED",
                    "The user's task explicitly requested this upload.",
                )
            return ConfirmationAssessment(
                ConfirmationMode.PREAPPROVAL,
                "UPLOAD_FILE",
                "Uploading a file requires explicit task preapproval or action-time confirmation.",
                f"Confirm that I may upload the selected file to this destination: {label[:180]}",
            )

        if self._LOGIN.search(label):
            domain = self._url_domain(observation.target.url or decision.url)
            login_implied = bool(domain and domain.casefold() in user_corpus.casefold())
            if login_implied or self._explicit(user_corpus, self._LOGIN):
                return ConfirmationAssessment(
                    ConfirmationMode.ALLOW,
                    "LOGIN_PREAPPROVED",
                    "Login is implied by the explicitly requested destination or task.",
                )
            return ConfirmationAssessment(
                ConfirmationMode.PREAPPROVAL,
                "LOGIN_OR_AUTHENTICATION",
                "Login was not clearly implied by the user's requested destination.",
                f"Confirm that I may continue with this login: {label[:180]}",
                sensitive=True,
            )

        if self._PERMISSION.search(label):
            if self._explicit(user_corpus, self._PERMISSION):
                return ConfirmationAssessment(
                    ConfirmationMode.ALLOW,
                    "PERMISSION_PREAPPROVED",
                    "The requested permission was explicitly preapproved.",
                )
            return ConfirmationAssessment(
                ConfirmationMode.PREAPPROVAL,
                "WINDOWS_OR_BROWSER_PERMISSION",
                "Camera, microphone, location, notification, or similar permissions require confirmation.",
                f"Confirm that I may grant this permission: {label[:180]}",
            )

        sensitive_transmission = bool(
            self._SENSITIVE_FIELD.search(label)
            and action_may_transmit(decision.action, label, decision.text)
        )
        if sensitive_transmission:
            explicit_specific = bool(
                self._SENSITIVE_FIELD.search(user_corpus)
                and action_may_transmit(decision.action, user_corpus, user_corpus)
            )
            if explicit_specific:
                return ConfirmationAssessment(
                    ConfirmationMode.ALLOW,
                    "SENSITIVE_TRANSMISSION_PREAPPROVED",
                    "The user explicitly named the sensitive data and transmission action.",
                )
            return ConfirmationAssessment(
                ConfirmationMode.PREAPPROVAL,
                "TRANSMIT_SENSITIVE_DATA",
                "Typing or submitting sensitive data to a third party requires destination-specific confirmation.",
                f"Confirm that I may transmit this sensitive data to the current destination: {label[:180]}",
                sensitive=True,
            )

        if injection_flagged and action_may_transmit(decision.action, label, decision.text):
            return ConfirmationAssessment(
                ConfirmationMode.ALWAYS_CONFIRM,
                "UNTRUSTED_CONTENT_TRANSMISSION",
                "Untrusted screen content contains possible instruction-injection indicators and the proposed action may transmit data.",
                "The page contains suspicious instructions. Confirm that this transmission is still part of your task.",
                sensitive=True,
            )

        return ConfirmationAssessment(
            ConfirmationMode.ALLOW,
            "ORDINARY_REVERSIBLE_ACTION",
            "Navigation, reading, scrolling, inspection, or reversible local configuration is allowed.",
        )
