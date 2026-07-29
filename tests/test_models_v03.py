import pytest
from pydantic import ValidationError

from agent_os.models import AgentDecision


def test_fill_element_requires_text() -> None:
    with pytest.raises(ValidationError):
        AgentDecision(action="fill_element", element_id="B001", reason="Fill field")


def test_smoke_test_site_accepts_link_limit() -> None:
    decision = AgentDecision(
        action="smoke_test_site",
        url="https://defytickets.com",
        max_links=40,
        reason="Test all same-origin links deterministically",
    )
    assert decision.max_links == 40


def test_smoke_signature_includes_limit_and_url() -> None:
    first = AgentDecision(
        action="smoke_test_site",
        url="https://example.com",
        max_links=20,
        reason="test",
    )
    second = AgentDecision(
        action="smoke_test_site",
        url="https://example.com",
        max_links=21,
        reason="test",
    )
    assert first.signature() != second.signature()
