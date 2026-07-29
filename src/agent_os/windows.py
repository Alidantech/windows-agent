from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from agent_os.models import Rectangle, UIElement, WindowInfo


@dataclass
class UIASnapshot:
    elements: list[UIElement]
    wrappers: dict[str, Any]


class WindowManager:
    """Windows-only helpers, imported lazily so non-Windows tests can run."""

    @staticmethod
    def _desktop():
        from pywinauto import Desktop

        return Desktop(backend="uia")

    @staticmethod
    def active_hwnd() -> int:
        import win32gui

        return int(win32gui.GetForegroundWindow())

    @staticmethod
    def _rect_from_wrapper(wrapper: Any) -> Rectangle:
        rect = wrapper.rectangle()
        return Rectangle(
            left=int(rect.left),
            top=int(rect.top),
            width=max(1, int(rect.right - rect.left)),
            height=max(1, int(rect.bottom - rect.top)),
        )

    def list_windows(self, limit: int = 100) -> list[WindowInfo]:
        import psutil

        active = self.active_hwnd()
        results: list[WindowInfo] = []
        for wrapper in self._desktop().windows(visible_only=True):
            try:
                title = (wrapper.window_text() or "").strip()
                if not title:
                    continue
                rect = self._rect_from_wrapper(wrapper)
                if rect.width < 40 or rect.height < 40:
                    continue
                hwnd = int(wrapper.handle)
                pid = int(wrapper.process_id())
                try:
                    process_name = psutil.Process(pid).name()
                except (psutil.Error, OSError):
                    process_name = None
                results.append(
                    WindowInfo(
                        hwnd=hwnd,
                        title=title,
                        process_id=pid,
                        process_name=process_name,
                        rect=rect,
                        active=hwnd == active,
                    )
                )
            except Exception:
                continue
        results.sort(key=lambda item: (not item.active, item.title.lower()))
        return results[:limit]

    def active_window(self) -> WindowInfo:
        import psutil
        import win32gui
        import win32process

        hwnd = self.active_hwnd()
        if not hwnd:
            raise RuntimeError("Windows did not report a foreground window.")

        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = max(1, int(right - left))
            height = max(1, int(bottom - top))
            title = (win32gui.GetWindowText(hwnd) or "").strip()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process_name = psutil.Process(pid).name()
            except (psutil.Error, OSError):
                process_name = None
            return WindowInfo(
                hwnd=hwnd,
                title=title or f"Foreground window {hwnd}",
                process_id=int(pid),
                process_name=process_name,
                rect=Rectangle(left=int(left), top=int(top), width=width, height=height),
                active=True,
            )
        except Exception:
            for window in self.list_windows(limit=300):
                if window.hwnd == hwnd:
                    return window
            raise RuntimeError("Could not resolve the active foreground window.") from None

    def find_window(self, title_pattern: str) -> WindowInfo:
        pattern = re.compile(title_pattern, re.IGNORECASE)
        matches = [window for window in self.list_windows(limit=300) if pattern.search(window.title)]
        if not matches:
            raise RuntimeError(f"No visible window title matched: {title_pattern!r}")
        return matches[0]

    def activate(self, title_pattern: str) -> WindowInfo:
        match = self.find_window(title_pattern)
        wrapper = self._desktop().window(handle=match.hwnd)
        try:
            wrapper.restore()
        except Exception:
            pass
        wrapper.set_focus()
        return match

    def snapshot_elements(
        self,
        hwnd: int,
        target_rect: Rectangle,
        max_elements: int,
    ) -> UIASnapshot:
        if max_elements <= 0:
            return UIASnapshot(elements=[], wrappers={})

        try:
            root = self._desktop().window(handle=hwnd)
            candidates = [root, *root.descendants()]
        except Exception:
            return UIASnapshot(elements=[], wrappers={})

        elements: list[UIElement] = []
        wrappers: dict[str, Any] = {}
        for wrapper in candidates:
            if len(elements) >= max_elements:
                break
            try:
                rect = self._rect_from_wrapper(wrapper)
                if rect.right <= target_rect.left or rect.left >= target_rect.right:
                    continue
                if rect.bottom <= target_rect.top or rect.top >= target_rect.bottom:
                    continue

                info = wrapper.element_info
                name = (getattr(info, "name", None) or wrapper.window_text() or "").strip()
                control_type = str(getattr(info, "control_type", "Unknown"))
                automation_id = getattr(info, "automation_id", None) or None
                visible = bool(wrapper.is_visible())
                enabled = bool(wrapper.is_enabled())
                if not visible:
                    continue
                if not name and not automation_id:
                    continue

                center_screen_x = rect.left + rect.width / 2
                center_screen_y = rect.top + rect.height / 2
                center_x = round((center_screen_x - target_rect.left) * 1000 / target_rect.width)
                center_y = round((center_screen_y - target_rect.top) * 1000 / target_rect.height)
                center_x = max(0, min(1000, center_x))
                center_y = max(0, min(1000, center_y))

                element_id = f"E{len(elements) + 1:03d}"
                element = UIElement(
                    element_id=element_id,
                    name=name[:200],
                    control_type=control_type[:80],
                    automation_id=str(automation_id)[:150] if automation_id else None,
                    enabled=enabled,
                    visible=visible,
                    rect=rect,
                    center_x=center_x,
                    center_y=center_y,
                )
                elements.append(element)
                wrappers[element_id] = wrapper
            except Exception:
                continue

        return UIASnapshot(elements=elements, wrappers=wrappers)
