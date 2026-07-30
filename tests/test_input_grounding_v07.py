from types import SimpleNamespace

from PIL import Image

from agent_os.interaction_policy import InteractionPolicy
from agent_os.models import AgentDecision, Rectangle, UIElement
from agent_os.overlay import _gradient_rectangles
from agent_os.task_contract import TaskContract
from agent_os.visual_grounding import render_set_of_mark


def test_navigation_only_scope_stops_at_requested_url():
    contract = TaskContract.from_task("open chrome and visit app.defytickets.co")
    assert contract.navigation_only is True
    assert contract.requested_url == "https://app.defytickets.co"
    assert contract.url_matches("https://app.defytickets.co/login?redirect=%2F")
    violation = contract.action_violation(
        AgentDecision(action="click_element", element_id="B0004", reason="create event")
    )
    assert violation is not None


def test_extended_browser_task_is_not_navigation_only():
    contract = TaskContract.from_task("open app.defytickets.co and create an event")
    assert contract.navigation_only is False


def test_set_of_mark_changes_model_copy_not_original():
    original = Image.new("RGB", (300, 160), "white")
    element = UIElement(
        element_id="B0001",
        name="Create event",
        control_type="button",
        rect=Rectangle(left=30, top=40, width=120, height=40),
        center_x=300,
        center_y=375,
        source="browser",
    )
    marked = render_set_of_mark(original, [element])
    assert original.getpixel((30, 40)) == (255, 255, 255)
    assert marked.getpixel((30, 40)) != (255, 255, 255)


def test_gradient_overlay_never_covers_monitor_center():
    monitor = Rectangle(left=1920, top=0, width=1920, height=1080)
    strips = _gradient_rectangles(monitor, depth=28, layers=10)
    center_x = monitor.left + monitor.width // 2
    center_y = monitor.top + monitor.height // 2
    assert len(strips) == 40
    assert not any(strip.contains(center_x, center_y) for strip, _alpha in strips)
    alphas = [alpha for _strip, alpha in strips]
    assert max(alphas) < 0.4
    assert min(alphas) < 0.03


def test_max_capacity_is_not_misclassified_as_address():
    element = UIElement(
        element_id="B0027",
        name="Max capacity (optional)",
        control_type="textbox",
        automation_id="event-address-max-capacity",
        rect=Rectangle(left=0, top=0, width=100, height=30),
        center_x=100,
        center_y=100,
        source="browser",
    )
    observation = SimpleNamespace(uia=SimpleNamespace(elements=[element]))
    decision = AgentDecision(
        action="fill_element",
        element_id="B0027",
        text="500",
        reason="fill capacity",
    )
    intervention = InteractionPolicy().required_intervention(
        decision,
        observation,
        task="create an event",
        guidance=[],
    )
    assert intervention is None


def test_grounded_browser_source_features_are_present():
    from agent_os.browser_precision import BrowserController

    source = repr(BrowserController._snapshot_elements.__code__.co_consts)
    assert "role=\"option\"" in source
    assert "data-windows-agent-id" in source
