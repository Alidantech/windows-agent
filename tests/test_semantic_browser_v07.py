from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from agent_os.agent import DesktopAgent
from agent_os.browser_semantic import BrowserController, SemanticBrowserElementRef
from agent_os.interaction_policy import InteractionPolicy
from agent_os.models import AgentDecision, Rectangle, UIElement
from agent_os.prompts import PromptBuilder


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


class _FakeLocator:
    def __init__(self, labels: list[str]):
        self.labels = labels

    @property
    def first(self):
        return self.nth(0)

    def count(self) -> int:
        return len(self.labels)

    def nth(self, index: int):
        return _FakeLocator([self.labels[index]])

    def is_visible(self) -> bool:
        return bool(self.labels)


class _FakePage:
    def __init__(self) -> None:
        self.live_option = _FakeLocator(["Live Performance"])
        self.empty = _FakeLocator([])

    def is_closed(self) -> bool:
        return False

    def locator(self, _selector: str):
        return self.empty

    def get_by_label(self, _name: str, exact: bool = True):
        return self.empty

    def get_by_role(self, role: str, name: str, exact: bool = True):
        if role == "option" and name == "Live Performance" and exact:
            return self.live_option
        return self.empty

    def get_by_text(self, _name: str, exact: bool = True):
        return self.empty

    def get_by_placeholder(self, _name: str, exact: bool = True):
        return self.empty


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


def test_stale_captured_selector_recovers_by_live_role_and_name() -> None:
    controller = BrowserController.__new__(BrowserController)
    controller._page = _FakePage()
    ref = SemanticBrowserElementRef(
        selector='[data-windows-agent-id="B0059"]',
        element_id="E0019",
        role="option",
        name="Live Performance",
    )
    resolved = controller._locator(ref)
    assert resolved.count() == 1
    assert resolved.labels == ["Live Performance"]


def test_full_page_candidates_are_pruned_without_losing_required_fields() -> None:
    actionables = [
        {
            "role": "link",
            "name": f"Navigation item {index}",
            "relation": "above",
            "documentY": index,
            "required": False,
            "enabled": True,
            "hasValue": True,
        }
        for index in range(180)
    ]
    actionables.append(
        {
            "role": "combobox",
            "name": "Category",
            "relation": "below",
            "documentY": 1400,
            "required": True,
            "enabled": True,
            "expanded": False,
            "hasValue": False,
        }
    )
    state = {
        "semantic_page": {
            "document": {"scrollTop": 0, "viewportHeight": 900},
            "actionables": actionables,
        }
    }
    pruned = PromptBuilder._prompt_observation_state(
        state,
        "complete the event form and select a category",
    )
    included = pruned["semantic_page"]["actionables"]
    assert len(included) == 120
    assert any(item["name"] == "Category" for item in included)
    assert pruned["semantic_page"]["pruning"]["original"] == 181


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
    assert DesktopAgent.__module__ == "agent_os.runtime_v12"
