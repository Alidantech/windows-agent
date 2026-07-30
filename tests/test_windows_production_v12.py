from __future__ import annotations

import pytest

from agent_os.models import Rectangle, WindowInfo
from agent_os.windows_production import WindowManager


def _window(hwnd: int, title: str, *, process: str = "app.exe", active: bool = False):
    return WindowInfo(
        hwnd=hwnd,
        title=title,
        process_id=1000 + hwnd,
        process_name=process,
        rect=Rectangle(left=0, top=0, width=800, height=600),
        active=active,
    )


def _manager(windows):
    manager = WindowManager.__new__(WindowManager)
    manager.list_windows = lambda limit=300: list(windows)
    return manager


def test_exact_window_title_is_selected() -> None:
    manager = _manager(
        [
            _window(1, "Project A - Editor"),
            _window(2, "Project B - Editor"),
        ]
    )
    assert manager.find_window("Project B - Editor").hwnd == 2


def test_ambiguous_window_query_is_rejected() -> None:
    manager = _manager(
        [
            _window(1, "Project A - Editor"),
            _window(2, "Project B - Editor"),
        ]
    )
    with pytest.raises(RuntimeError, match="ambiguous"):
        manager.find_window("Editor")


def test_process_target_uses_only_unique_active_window() -> None:
    manager = _manager(
        [
            _window(1, "Document 1", process="writer.exe"),
            _window(2, "Document 2", process="writer.exe", active=True),
        ]
    )
    assert manager.find_process_window("writer.exe").hwnd == 2


def test_process_target_rejects_multiple_inactive_windows() -> None:
    manager = _manager(
        [
            _window(1, "Document 1", process="writer.exe"),
            _window(2, "Document 2", process="writer.exe"),
        ]
    )
    with pytest.raises(RuntimeError, match="no unique active target"):
        manager.find_process_window("writer")
