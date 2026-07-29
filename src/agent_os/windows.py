from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageStat

from agent_os.models import Rectangle, UIElement, WindowInfo
from agent_os.targeting import best_window_match, window_match_score


@dataclass
class UIASnapshot:
    elements: list[UIElement]
    wrappers: dict[str, Any]


class WindowManager:
    BROWSER_PROCESSES = {"chrome.exe", "msedge.exe", "brave.exe", "firefox.exe"}

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

    @staticmethod
    def _window_info(hwnd: int, active: int | None = None) -> WindowInfo:
        import psutil
        import win32gui
        import win32process

        if not win32gui.IsWindow(hwnd):
            raise RuntimeError(f"Window handle {hwnd} no longer exists.")
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            process_name = psutil.Process(pid).name()
        except (psutil.Error, OSError):
            process_name = None
        return WindowInfo(
            hwnd=int(hwnd),
            title=(win32gui.GetWindowText(hwnd) or "").strip() or f"Window {hwnd}",
            process_id=int(pid),
            process_name=process_name,
            rect=Rectangle(
                left=int(left),
                top=int(top),
                width=max(1, int(right - left)),
                height=max(1, int(bottom - top)),
            ),
            active=int(hwnd) == int(active or -1),
        )

    def list_windows(self, limit: int = 100) -> list[WindowInfo]:
        active = self.active_hwnd()
        results: list[WindowInfo] = []
        seen: set[int] = set()
        for wrapper in self._desktop().windows(visible_only=True):
            try:
                hwnd = int(wrapper.handle)
                if hwnd in seen:
                    continue
                seen.add(hwnd)
                info = self._window_info(hwnd, active)
                if not info.title or info.rect.width < 40 or info.rect.height < 40:
                    continue
                results.append(info)
            except Exception:
                continue
        results.sort(key=lambda item: (not item.active, item.title.lower()))
        return results[:limit]

    def window_by_hwnd(self, hwnd: int) -> WindowInfo:
        return self._window_info(hwnd, self.active_hwnd())

    def active_window(self) -> WindowInfo:
        hwnd = self.active_hwnd()
        if not hwnd:
            raise RuntimeError("Windows did not report a foreground window.")
        return self.window_by_hwnd(hwnd)

    def find_window(self, query: str) -> WindowInfo:
        windows = self.list_windows(limit=300)
        match = best_window_match(query, windows)
        if match is not None:
            return match
        suggestions = sorted(
            windows,
            key=lambda item: window_match_score(query, item),
            reverse=True,
        )[:5]
        nearest = ", ".join(repr(item.title) for item in suggestions) or "none"
        raise RuntimeError(f"No visible window matched {query!r}. Closest titles: {nearest}")

    def find_process_window(self, process: str) -> WindowInfo:
        normalized = process.lower().removesuffix(".exe")
        matches = [
            item
            for item in self.list_windows(limit=300)
            if (item.process_name or "").lower().removesuffix(".exe") == normalized
        ]
        if not matches:
            raise RuntimeError(f"No visible window belongs to process {process!r}.")
        return sorted(matches, key=lambda item: item.active, reverse=True)[0]

    def activate_hwnd(self, hwnd: int) -> WindowInfo:
        import win32con
        import win32gui

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            self._desktop().window(handle=hwnd).set_focus()
        except Exception:
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception as exc:
                raise RuntimeError(f"Could not activate window {hwnd}: {exc}") from exc
        return self.window_by_hwnd(hwnd)

    def activate(self, query: str) -> WindowInfo:
        match = self.find_window(query)
        return self.activate_hwnd(match.hwnd)

    @staticmethod
    def monitor_for_rect(rect: Rectangle, monitors: list[tuple[int, Rectangle]]) -> int | None:
        center_x = rect.left + rect.width / 2
        center_y = rect.top + rect.height / 2
        for index, monitor in monitors:
            if monitor.contains(center_x, center_y):
                return index
        if not monitors:
            return None
        return max(monitors, key=lambda item: rect.intersection_area(item[1]))[0]

    def move_to_monitor(self, hwnd: int, monitor: Rectangle, maximize: bool = True) -> WindowInfo:
        import win32con
        import win32gui

        current = self.window_by_hwnd(hwnd)
        try:
            if win32gui.IsIconic(hwnd) or win32gui.IsZoomed(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        except Exception:
            pass
        width = min(max(720, current.rect.width), monitor.width)
        height = min(max(520, current.rect.height), monitor.height)
        left = monitor.left + max(0, (monitor.width - width) // 2)
        top = monitor.top + max(0, (monitor.height - height) // 2)
        if not win32gui.MoveWindow(hwnd, left, top, width, height, True):
            raise RuntimeError(f"Could not move {current.title!r} to the assigned monitor.")
        if maximize:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            except Exception:
                pass
        return self.window_by_hwnd(hwnd)

    def capture_window_image(self, hwnd: int) -> Image.Image | None:
        import win32gui
        import win32ui

        window = self.window_by_hwnd(hwnd)
        width, height = window.rect.width, window.rect.height
        hwnd_dc = 0
        source_dc = None
        memory_dc = None
        bitmap = None
        try:
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            if not hwnd_dc:
                return None
            source_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            memory_dc = source_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(source_dc, width, height)
            memory_dc.SelectObject(bitmap)
            result = ctypes.windll.user32.PrintWindow(hwnd, memory_dc.GetSafeHdc(), 0x00000002)
            if result != 1:
                return None
            raw = bitmap.GetBitmapBits(True)
            image = Image.frombuffer("RGB", (width, height), raw, "raw", "BGRX", 0, 1).copy()
            stats = ImageStat.Stat(image.resize((64, 64)))
            if max(stats.var) < 1.0 and max(stats.mean) < 8.0:
                return None
            return image
        except Exception:
            return None
        finally:
            try:
                if bitmap is not None:
                    win32gui.DeleteObject(bitmap.GetHandle())
            except Exception:
                pass
            try:
                if memory_dc is not None:
                    memory_dc.DeleteDC()
            except Exception:
                pass
            try:
                if source_dc is not None:
                    source_dc.DeleteDC()
            except Exception:
                pass
            try:
                if hwnd_dc:
                    win32gui.ReleaseDC(hwnd, hwnd_dc)
            except Exception:
                pass

    @staticmethod
    def semantic_invoke(wrapper: Any) -> str | None:
        for method_name in ("invoke", "select", "toggle", "expand", "click"):
            method = getattr(wrapper, method_name, None)
            if callable(method):
                try:
                    method()
                    return method_name
                except Exception:
                    pass
        try:
            wrapper.iface_invoke.Invoke()
            return "InvokePattern"
        except Exception:
            return None

    @staticmethod
    def semantic_set_text(wrapper: Any, text: str) -> str | None:
        for method_name in ("set_edit_text", "set_text"):
            method = getattr(wrapper, method_name, None)
            if callable(method):
                try:
                    method(text)
                    return method_name
                except Exception:
                    pass
        try:
            wrapper.iface_value.SetValue(text)
            return "ValuePattern"
        except Exception:
            return None

    @staticmethod
    def focused_wrapper(snapshot: UIASnapshot) -> tuple[str, Any] | None:
        for element_id, wrapper in snapshot.wrappers.items():
            try:
                if wrapper.has_keyboard_focus():
                    return element_id, wrapper
            except Exception:
                continue
        return None

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
                if not wrapper.is_visible() or (not name and not automation_id):
                    continue
                cx = rect.left + rect.width / 2
                cy = rect.top + rect.height / 2
                center_x = round((cx - target_rect.left) * 1000 / target_rect.width)
                center_y = round((cy - target_rect.top) * 1000 / target_rect.height)
                element_id = f"E{len(elements) + 1:03d}"
                elements.append(
                    UIElement(
                        element_id=element_id,
                        name=name[:200],
                        control_type=control_type[:80],
                        automation_id=str(automation_id)[:150] if automation_id else None,
                        enabled=bool(wrapper.is_enabled()),
                        visible=True,
                        rect=rect,
                        center_x=max(0, min(1000, center_x)),
                        center_y=max(0, min(1000, center_y)),
                        source="uia",
                    )
                )
                wrappers[element_id] = wrapper
            except Exception:
                continue
        return UIASnapshot(elements=elements, wrappers=wrappers)
