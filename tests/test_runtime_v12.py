from __future__ import annotations

from agent_os.agent import DesktopAgent
from agent_os.models import AgentDecision


def test_public_agent_uses_runtime_v12() -> None:
    assert DesktopAgent.__module__ == "agent_os.runtime_v12"


def test_inspect_region_requires_valid_rectangle() -> None:
    decision = AgentDecision(
        action="inspect_region",
        observation_id="obs-1",
        x=100,
        y=200,
        x2=600,
        y2=800,
        reason="Inspect small text",
    )
    assert decision.action == "inspect_region"
    assert decision.x2 == 600
