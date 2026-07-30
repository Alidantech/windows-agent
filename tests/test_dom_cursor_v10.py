from __future__ import annotations

import inspect

import agent_os.runtime_v10 as runtime_v10
from agent_os.browser_precision_v4 import BrowserController
from agent_os.overlay_edges import EdgeOverlay, _process_main


def test_virtual_cursor_is_rendered_inside_the_browser_page() -> None:
    source = inspect.getsource(BrowserController._show_virtual_cursor)
    assert "👆🏻" in source
    assert "pointerEvents: 'none'" in source
    assert "attachShadow" in source
    assert "page.evaluate" in source


def test_browser_cursor_is_hidden_during_model_capture() -> None:
    source = inspect.getsource(BrowserController.capture)
    assert "_hide_virtual_cursor" in source
    assert "_show_virtual_cursor" in source


def test_edge_overlay_never_creates_a_cursor_window() -> None:
    source = inspect.getsource(_process_main)
    assert "ImageTk" not in source
    assert "PhotoImage" not in source
    assert "👆🏻" not in source
    EdgeOverlay().cursor(100, 200, "click")


def test_active_runtime_does_not_inherit_legacy_hand_overlay() -> None:
    source = inspect.getsource(runtime_v10)
    assert "runtime_v09" not in source
    assert "HandOverlay" not in source
    assert "EdgeOverlay" in source
    assert "browser_precision_v4" in source
