from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_DEMO = re.compile(
    r"\b(?:demo|sample|test|mock|dummy|placeholder|fictional|fake)\b",
    re.IGNORECASE,
)
_DELEGATION = re.compile(
    r"\b(?:"
    r"(?:fill|complete|choose|pick|decide|handle|set)\b.{0,50}\b"
    r"(?:yourself|for\s+me|on\s+your\s+own)|"
    r"(?:use|choose|pick)\s+(?:reasonable\s+)?(?:defaults?|values?|details?)|"
    r"make\s+(?:it|them|the\s+values?)\s+up|"
    r"be\s+autonomous|just\s+(?:fill|complete|choose|decide|do)"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)
_WORKFLOW_AUTONOMY = re.compile(
    r"\b(?:complete|finish|fill|follow|continue|set\s*up|setup)\b.{0,80}\b"
    r"(?:form|event|setup|set[- ]?up|workflow|process)\b|"
    r"\b(?:complete|finish|fill)\s+(?:all\s+)?(?:required\s+)?"
    r"(?:fields|details|values)\b",
    re.IGNORECASE | re.DOTALL,
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
_GRANT_VALUE = re.compile(r"^-\s+([^:\n]+):\s*(.+?)\s*$", re.MULTILINE)
_CANONICAL_DEFAULT_KEYS = {
    "event title": "event title",
    "short name": "short name",
    "event url slug": "event URL slug",
    "start date and time": "start date and time",
    "end date and time": "end date and time",
    "max capacity": "max capacity",
}


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
                "When active, choose and use the supplied reversible non-personal values "
                "without asking again. Ask only for protected identity, credentials, consent, "
                "payment, verification, publishing, sending, deletion, or a material ambiguity "
                "that cannot be resolved safely from the page."
            ),
        }

    def instruction(self) -> str:
        if not self.active:
            return ""
        lines = [
            _GRANT_MARKER,
            "The user authorizes autonomous reversible non-personal choices for this task.",
            "Do not ask again for ordinary form fields covered below.",
            "Use these exact values when matching fields exist:",
        ]
        lines.extend(f"- {key}: {value}" for key, value in self.defaults.items())
        lines.extend(
            [
                "- category preference: Technology, then Conference, then Workshop, then Other",
                "- timezone preference: keep a valid current value; otherwise Africa/Nairobi, then UTC",
                "- optional fields: leave blank unless useful or required to advance",
                "- seating preference: General Admission",
                "- online/broadcast preference: No unless online delivery was requested",
                "This grant does not authorize personal identity, credentials, legal consent, "
                "payment, CAPTCHA/OTP, publishing, sending, deletion, or other irreversible actions.",
            ]
        )
        return "\n".join(lines)


def _event_defaults(now: datetime | None = None) -> dict[str, str]:
    try:
        zone = ZoneInfo("Africa/Nairobi")
    except Exception:
        zone = timezone(timedelta(hours=3), name="EAT")
    current = now or datetime.now(zone)
    if current.tzinfo is None:
        current = current.replace(tzinfo=zone)
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


def _stored_defaults(corpus: str) -> dict[str, str]:
    if _GRANT_MARKER not in corpus:
        return {}
    values: dict[str, str] = {}
    for key, value in _GRANT_VALUE.findall(corpus):
        normalized = " ".join(key.strip().casefold().split())
        canonical = _CANONICAL_DEFAULT_KEYS.get(normalized)
        if canonical:
            values[canonical] = value.strip()
    return values


def autonomy_grant(
    task: str,
    guidance: list[str] | tuple[str, ...] = (),
    *,
    now: datetime | None = None,
) -> AutonomyGrant:
    corpus = "\n".join([task, *guidance])
    if _GRANT_MARKER in corpus:
        stored = _stored_defaults(corpus)
        return AutonomyGrant(
            True,
            "a prior autonomy grant is active",
            stored or (_event_defaults(now) if _EVENT.search(corpus) else {}),
        )
    has_demo = bool(_DEMO.search(corpus))
    delegated = bool(_DELEGATION.search(corpus))
    workflow = bool(_WORKFLOW_AUTONOMY.search(corpus))
    if not (has_demo or delegated or workflow):
        return AutonomyGrant(False, "no autonomous workflow authorization", {})
    if has_demo:
        reason = "the user requested demo/sample/test data"
    elif delegated:
        reason = "the user delegated reversible non-personal choices"
    else:
        reason = "the user requested completion of a reversible form workflow"
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
