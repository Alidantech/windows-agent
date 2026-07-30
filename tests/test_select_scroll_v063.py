from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

from agent_os.browser_precision_v4 import BrowserController
from agent_os.runtime_v10 import DesktopAgent
from agent_os.tools_controls import ToolExecutor


def test_select_controls_are_classified_explicitly() -> None:
    assert ToolExecutor._is_select_control(
        SimpleNamespace(control_type="combobox", tag="button")
    )
    assert ToolExecutor._is_select_control(
        SimpleNamespace(control_type="select", tag="select")
    )
    assert not ToolExecutor._is_select_control(
        SimpleNamespace(control_type="textbox", tag="input")
    )


def test_browser_controller_has_verified_select_path() -> None:
    source = inspect.getsource(BrowserController.select_option_state)
    assert "select_option" in source
    assert "get_by_role(\"option\")" in inspect.getsource(
        BrowserController._visible_options
    )
    assert "selected" in source


def test_browser_controller_measures_scroll_movement() -> None:
    source = inspect.getsource(BrowserController.scroll_state)
    assert "mouse.wheel" in source
    assert "observed_pixels" in source
    assert "at_start" in source
    assert "at_end" in source
    assert "_fallback_scroll" in source


def test_planner_prompt_documents_select_and_scroll_contract() -> None:
    prompt = Path("prompts/system.md").read_text(encoding="utf-8")
    assert "use `fill_element` on the select or combobox" in prompt
    assert "positive to scroll down and negative to scroll up" in prompt
    assert "Never repeatedly click an already-open combobox" in prompt
    assert "test system cursor access" in prompt


def test_active_runtime_uses_control_executor() -> None:
    source = inspect.getsource(DesktopAgent.__init__)
    assert "ToolExecutor(" in source
    assert "self.browser" in source
    assert "self.overlay" in source
