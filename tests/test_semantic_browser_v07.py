from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from agent_os.agent import DesktopAgent
from agent_os.browser_semantic import SemanticBrowserElementRef
from agent_os.interaction_policy import InteractionPolicy
from agent_os.models import AgentDecision, Rectangle, UIElement


def _observation(element: UIElement):
    return SimpleNamespace(uia=SimpleNamespace(elements=[element]))


def _element(name: str, role: str = "combobox") -> UIElement:
    return UIElement(
        element_id="E0001",
        name=name,
        control_type=role,
        rect=Rectangle(left=0, top=0, width=200, height=40),
        center_x=100,
        center_y=100,
        source="browser",
        editable=True,
        required=True,
        has_value=False,
    )


def test_select_option_is_a_typed_action() -> None:
    decision = AgentDecision(
        action="select_option",
        element_id="E0001",
        option="Live Performance",
        reason="Select an option exposed by the current category combobox.",
    )
    assert decision.option == "Live Performance"
    assert "Live Performance" in decision.signature()


def test_select_option_requires_exact_option_text() -> None:
    with pytest.raises(ValidationError):
        AgentDecision(
            action="select_option",
            element_id="E0001",
            reason="Missing option should be rejected before execution.",
        )


def test_semantic_reference_carries_live_locator_fingerprint() -> None:
    ref = SemanticBrowserElementRef(
        selector='[data-windows-agent-id="B0059"]',
        element_id="E0019",
        role="combobox",
        name="Category",
        automation_id="category",
        form_id="create-event",
    )
    assert ref.element_id == "E0019"
    assert ref.role == "combobox"
    assert ref.name == "Category"
    assert ref.automation_id == "category"


def test_ordinary_semantic_select_does_not_interrupt() -> None:
    decision = AgentDecision(
        action="select_option",
        element_id="E0001",
        option="Live Performance",
        reason="Choose a reversible event category.",
    )
    intervention = InteractionPolicy().required_intervention(
        decision,
        _observation(_element("Category")),
        task="complete the create event form",
        guidance=[],
    )
    assert intervention is None


def test_personal_semantic_select_remains_protected() -> None:
    decision = AgentDecision(
        action="select_option",
        element_id="E0001",
        option="Personal account",
        reason="Choose an account username option.",
    )
    intervention = InteractionPolicy().required_intervention(
        decision,
        _observation(_element("Username")),
        task="complete the account form",
        guidance=[],
    )
    assert intervention is not None
    assert intervention.sensitive is True


def test_active_agent_uses_semantic_runtime() -> None:
    assert DesktopAgent.__module__ == "agent_os.runtime_v11"
