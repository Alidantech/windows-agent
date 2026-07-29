from agent_os.models import Rectangle
from agent_os.overlay import NullOverlay, create_overlay


def test_disabled_overlay_is_noop() -> None:
    overlay = create_overlay(False)
    assert isinstance(overlay, NullOverlay)
    overlay.start(Rectangle(left=0, top=0, width=100, height=100), "test")
    overlay.status("working")
    overlay.cursor(20, 20, "click")
    overlay.stop()
