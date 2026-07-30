from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from agent_os.autonomy import autonomy_grant, expand_user_answer, question_can_use_grant
from agent_os.intent import IntentRouter


def test_typo_create_event_continues_active_browser() -> None:
    intent = IntentRouter().route("creaye an event", browser_active=True)
    assert intent.kind == "desktop"
    assert intent.continue_browser is True


def test_use_browser_continues_active_browser() -> None:
    intent = IntentRouter().route("use the browser", browser_active=True)
    assert intent.kind == "desktop"
    assert intent.continue_browser is True


def test_demo_event_creates_reversible_defaults() -> None:
    now = datetime(2026, 7, 30, 13, 48, tzinfo=ZoneInfo("Africa/Nairobi"))
    grant = autonomy_grant("help me create a demo event", now=now)
    assert grant.active is True
    assert grant.defaults["event title"] == "Windows Agent Demo Event"
    assert grant.defaults["event URL slug"].startswith("windows-agent-demo-20260730-")
    assert grant.defaults["start date and time"].startswith("2026-07-31T10:00")
    assert grant.defaults["end date and time"].startswith("2026-07-31T12:00")


def test_demo_answer_expands_into_stable_plan() -> None:
    now = datetime(2026, 7, 30, 13, 48, tzinfo=ZoneInfo("Africa/Nairobi"))
    expanded = expand_user_answer(
        "just fill yourself",
        "Please provide the event title, slug, category, timezone and dates.",
        now=now,
    )
    assert "WINDOWS_AGENT_AUTONOMY_GRANT" in expanded
    assert "Windows Agent Demo Event" in expanded
    assert "Do not ask again" in expanded


def test_grant_never_auto_answers_protected_questions() -> None:
    assert question_can_use_grant("Which category should the demo event use?") is True
    assert question_can_use_grant("What email address should I use?") is False
    assert question_can_use_grant("Should I accept the terms?") is False
