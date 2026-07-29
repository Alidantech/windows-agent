import pytest
from pydantic import ValidationError

from agent_os.models import AgentDecision


def test_click_requires_coordinates() -> None:
    with pytest.raises(ValidationError):
        AgentDecision(action="click", reason="click it")


def test_start_menu_semantic_key_is_valid() -> None:
    decision = AgentDecision(action="press_key", key="win", reason="Open Start semantically")
    assert decision.key == "win"


def test_signature_is_stable() -> None:
    first = AgentDecision(action="click", x=500, y=500, reason="a")
    second = AgentDecision(action="click", x=500, y=500, reason="different wording")
    assert first.signature() == second.signature()


def test_open_url_requires_url() -> None:
    with pytest.raises(ValidationError):
        AgentDecision(action="open_url", reason="Open website")


def test_open_url_accepts_optional_browser() -> None:
    decision = AgentDecision(
        action="open_url",
        url="https://chatgpt.com",
        browser="chrome",
        reason="Open ChatGPT in Chrome",
    )
    assert decision.browser == "chrome"
