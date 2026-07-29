from types import SimpleNamespace

from agent_os.models import Rectangle
from agent_os.tools import ToolExecutor


def observation(left: int, top: int, width: int, height: int):
    return SimpleNamespace(
        target=SimpleNamespace(rect=Rectangle(left=left, top=top, width=width, height=height))
    )


def test_normalized_coordinate_center() -> None:
    point = ToolExecutor._screen_point(observation(0, 0, 1920, 1080), 500, 500)
    assert point == (960, 540)


def test_normalized_coordinate_handles_negative_monitor_origin() -> None:
    point = ToolExecutor._screen_point(observation(-1920, 0, 1920, 1080), 500, 500)
    assert point == (-960, 540)


def test_normalized_bottom_right_stays_inside_target() -> None:
    point = ToolExecutor._screen_point(observation(100, 50, 800, 600), 1000, 1000)
    assert point == (899, 649)
