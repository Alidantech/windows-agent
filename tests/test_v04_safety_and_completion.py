import pytest

from agent_os.cancellation import AgentCancelled, CancellationToken
from agent_os.models import ExecutionResult, Rectangle
from agent_os.overlay import AgentOverlay, _gradient_rectangles


def test_cancellation_token_interrupts_wait() -> None:
    token = CancellationToken()
    token.cancel("stop now")
    assert token.cancelled
    assert token.wait(0.01)
    with pytest.raises(AgentCancelled, match="stop now"):
        token.raise_if_cancelled()


def test_cancellation_token_can_reset_for_chat_next_task() -> None:
    token = CancellationToken()
    token.cancel()
    token.reset()
    assert not token.cancelled
    token.raise_if_cancelled()


def test_safe_overlay_geometry_supports_negative_monitors() -> None:
    assert AgentOverlay._geometry(100, 50, -1920, 0) == "100x50-1920+0"
    assert AgentOverlay._geometry(100, 50, 1920, -1080) == "100x50+1920-1080"


def test_deterministic_tool_result_can_complete_task() -> None:
    result = ExecutionResult(
        ok=True,
        summary="Smoke-tested all links.",
        task_complete=True,
        completion_evidence="Report contains all unique links.",
    )
    assert result.task_complete
    assert result.completion_evidence


def test_overlay_layout_never_contains_monitor_sized_window() -> None:
    monitor = Rectangle(left=1920, top=0, width=1920, height=1080)
    strips = tuple(strip for strip, _alpha in _gradient_rectangles(monitor))
    center_x = monitor.left + monitor.width // 2
    center_y = monitor.top + monitor.height // 2

    assert len(strips) == 40
    assert all(strip.width < monitor.width or strip.height < monitor.height for strip in strips)
    assert not any(strip.contains(center_x, center_y) for strip in strips)
    assert sum(strip.width * strip.height for strip in strips) < (
        monitor.width * monitor.height // 8
    )
