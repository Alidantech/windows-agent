from agent_os.browser import BrowserController


def test_browser_key_aliases() -> None:
    assert BrowserController._key("win") == "Meta"
    assert BrowserController._key("left") == "ArrowLeft"
    assert BrowserController._key("f5") == "F5"


def test_screen_point_uses_viewport_rect_without_real_cursor(monkeypatch) -> None:
    controller = object.__new__(BrowserController)
    monkeypatch.setattr(
        controller,
        "viewport_screen_rect",
        lambda: __import__("agent_os.models", fromlist=["Rectangle"]).Rectangle(
            left=1920, top=90, width=1920, height=990
        ),
    )
    assert controller.screen_point(500, 500) == (2880, 584)
