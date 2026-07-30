from types import SimpleNamespace

from agent_os.config import Settings
from agent_os.intent import IntentRouter
from agent_os.interaction_policy import InteractionPolicy
from agent_os.local_values import LOCAL_VALUE_TOKEN, local_value_vault
from agent_os.models import AgentDecision, Rectangle, UIElement
from agent_os.tools_runtime import ToolExecutor


def element(**overrides):
    values = {
        "element_id": "B0001",
        "name": "Event title *",
        "control_type": "textbox",
        "rect": Rectangle(left=0, top=0, width=100, height=30),
        "center_x": 100,
        "center_y": 100,
        "source": "browser",
        "editable": True,
        "required": True,
        "has_value": False,
    }
    values.update(overrides)
    return UIElement(**values)


def observation(item):
    return SimpleNamespace(uia=SimpleNamespace(elements=[item]))


def test_event_creation_follow_up_routes_to_active_browser():
    router = IntentRouter()
    intent = router.route("create an event", browser_active=True)
    assert intent.kind == "desktop"
    assert intent.continue_browser is True


def test_follow_event_creation_routes_to_active_browser():
    intent = IntentRouter().route(
        "follow event creation process",
        browser_active=True,
    )
    assert intent.kind == "desktop"
    assert intent.continue_browser is True


def test_non_computer_create_request_stays_conversation():
    assert IntentRouter().route("create a poem").kind == "conversation"


def test_required_authored_value_prompts_without_masking():
    decision = AgentDecision(
        action="fill_element",
        element_id="B0001",
        text="Placeholder Event",
        reason="fill title",
    )
    intervention = InteractionPolicy().required_intervention(
        decision,
        observation(element()),
        task="create an event",
        guidance=[],
    )
    assert intervention is not None
    assert intervention.sensitive is False
    assert "Event title" in intervention.question


def test_explicit_required_value_is_allowed():
    decision = AgentDecision(
        action="fill_element",
        element_id="B0001",
        text="Nairobi Tech Night",
        reason="fill title",
    )
    intervention = InteractionPolicy().required_intervention(
        decision,
        observation(element()),
        task="create an event titled Nairobi Tech Night",
        guidance=[],
    )
    assert intervention is None


def test_generic_local_value_is_scoped_to_exact_field():
    local_value_vault.clear()
    local_value_vault.set(
        "Nairobi Tech Night",
        purpose="What value should I enter for required field 'Event title *'?",
    )
    assert local_value_vault.matches_target("Event title * textbox")
    assert not local_value_vault.matches_target("Short name * textbox")
    local_value_vault.clear()


def test_local_token_is_allowed_for_matching_required_field():
    local_value_vault.clear()
    local_value_vault.set(
        "Nairobi Tech Night",
        purpose="What value should I enter for required field 'Event title *'?",
    )
    decision = AgentDecision(
        action="fill_element",
        element_id="B0001",
        text=LOCAL_VALUE_TOKEN,
        reason="use local value",
    )
    intervention = InteractionPolicy().required_intervention(
        decision,
        observation(element()),
        task="create an event",
        guidance=[],
    )
    assert intervention is None
    local_value_vault.clear()


def test_cursor_mode_defaults_to_virtual():
    assert Settings().cursor_mode == "virtual"


def test_submit_error_summary_lists_missing_fields():
    summary = ToolExecutor._invalid_summary(
        {
            "missing_required": ["Event URL", "Category"],
            "invalid_fields": [{"name": "Start date", "message": "Choose a future date"}],
        }
    )
    assert "Event URL" in summary
    assert "Category" in summary
    assert "Choose a future date" in summary
