from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_DEMO = re.compile(
    r"\b(?:demo|sample|test|mock|dummy|placeholder|fictional|fake)\b",
    re.IGNORECASE,
)
_DELEGATION = re.compile(
    r"\b(?:fill\s+(?:it\s+)?yourself|choose\s+(?:the\s+)?(?:details|values|defaults)|"
    r"use\s+(?:reasonable\s+)?defaults|make\s+(?:it|them)\s+up|decide\s+for\s+me|"
    r"handle\s+(?:the\s+)?details|do\s+it\s+yourself|just\s+fill|be\s+autonomous)\b",
    re.IGNORECASE,
)
_EVENT = re.compile(
    r"\b(?:event|event\s+title|short\s+name|slug|event\s+url|category|timezone|"
    r"start\s+date|end\s+date|seating|general\s+admission|livestream|venue|capacity)\b",
    re.IGNORECASE,
)
_PROTECTED = re.compile(
    r"\b(?:password|passcode|pin|otp|verification\s+code|security\s+code|2fa|mfa|"
    r"captcha|human\s+verification|terms|privacy|consent|subscribe|newsletter|"
    r"payment|card|bank|purchase|buy|publish|send|delete|remove|refund|"
    r"first\s+name|last\s+name|full\s+name|email|phone|address|company|"
    r"organisation|organization|username|date\s+of\s+birth|birthday)\b",
    re.IGNORECASE,
)
_GRANT_MARKER = "WINDOWS_AGENT_AUTONOMY_GRANT"


@dataclass(frozen=True)
class AutonomyGrant:
    active: bool
    reason: str
    defaults: dict[str, str]

    def as_prompt_context(self) -> dict[str, object]:
        return {
            "active": self.active,
            "reason": self.reason,
            "defaults": self.defaults,
            "rules": (
                "When active, choose and use the supplied reversible non-personal demo "
                "defaults without asking again. Ask only for protected identity, credentials, "
                "consent, payment, verification, publishing, sending, deletion, or a material "
                "ambiguity not covered by the defaults."
            ),
        }

    def instruction(self) -> str:
        if not self.active:
            return ""
        lines = [
            _GRANT_MARKER,
            "The user explicitly authorizes autonomous reversible demo/test data for this task.",
            "Do not ask again for non-sensitive demo fields covered below.",
            "Use these exact values when matching fields exist:",
        ]
        lines.extend(f"- {key}: {value}" for key, value in self.defaults.items())
        lines.extend(
            [
                "- category: prefer Technology, then Conference, then Workshop, then Other",
                "- timezone: keep the current valid value; otherwise prefer Africa/Nairobi, then UTC",
                "- optional fields: leave blank unless needed to advance",
                "- seating: prefer General Admission",
                "- online/broadcast: choose No unless the task explicitly requests online delivery",
                "This grant does not authorize personal identity, credentials, legal consent, "
                "payment, CAPTCHA/OTP, publishing, sending, deletion, or other irreversible actions.",
            ]
        )
        return "\n".join(lines)


def _event_defaults(now: datetime | None = None) -> dict[str, str]:
    try:
        zone = ZoneInfo("Africa/Nairobi")
    except Exception:
        zone = None
    current = now or datetime.now(zone).astimezone()
    if current.tzinfo is None:
        current = current.astimezone()
    start_date = (current + timedelta(days=1)).date()
    start = datetime.combine(start_date, datetime.min.time(), current.tzinfo).replace(hour=10)
    end = start + timedelta(hours=2)
    stamp = current.strftime("%Y%m%d-%H%M%S")
    return {
        "event title": "Windows Agent Demo Event",
        "short name": "Agent Demo",
        "event URL slug": f"windows-agent-demo-{stamp}",
        "start date and time": start.isoformat(timespec="minutes"),
        "end date and time": end.isoformat(timespec="minutes"),
        "max capacity": "100",
    }


def autonomy_grant(
    task: str,
    guidance: list[str] | tuple[str, ...] = (),
    *,
    now: datetime | None = None,
) -> AutonomyGrant:
    corpus = "\n".join([task, *guidance])
    if _GRANT_MARKER in corpus:
        return AutonomyGrant(True, "a prior autonomy grant is active", _event_defaults(now))
    has_demo = bool(_DEMO.search(corpus))
    delegated = bool(_DELEGATION.search(corpus))
    if not (has_demo or delegated):
        return AutonomyGrant(False, "no demo or delegation authorization", {})
    reason = (
        "the user requested demo/sample/test data"
        if has_demo
        else "the user delegated reversible non-personal choices"
    )
    defaults = _event_defaults(now) if _EVENT.search(corpus) else {}
    return AutonomyGrant(True, reason, defaults)


def allows_demo_inference(task: str, guidance: list[str] | tuple[str, ...] = ()) -> bool:
    return autonomy_grant(task, guidance).active


def question_can_use_grant(question: str) -> bool:
    return bool(_EVENT.search(question)) and not bool(_PROTECTED.search(question))


def expand_user_answer(
    answer: str,
    question: str,
    *,
    now: datetime | None = None,
) -> str:
    grant = autonomy_grant(
        f"{question}\n{answer}",
        (),
        now=now,
    )
    if not grant.active or not question_can_use_grant(question):
        return answer
    return f"{answer.strip()}\n\n{grant.instruction()}"
