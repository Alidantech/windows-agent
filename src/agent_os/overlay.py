from __future__ import annotations

import multiprocessing as mp
import platform
import queue
from dataclasses import dataclass
from typing import Any, Protocol

from agent_os.models import Rectangle


class Overlay(Protocol):
    def start(self, rect: Rectangle, label: str) -> None: ...
    def status(self, text: str, state: str = "ready") -> None: ...
    def cursor(self, x: int, y: int, action: str) -> None: ...
    def stop(self) -> None: ...


class NullOverlay:
    def start(self, rect: Rectangle, label: str) -> None:
        return

    def status(self, text: str, state: str = "ready") -> None:
        return

    def cursor(self, x: int, y: int, action: str) -> None:
        return

    def stop(self) -> None:
        return


@dataclass(frozen=True)
class OverlayEvent:
    kind: str
    payload: dict[str, object]


def _geometry(width: int, height: int, left: int, top: int) -> str:
    x = f"+{left}" if left >= 0 else str(left)
    y = f"+{top}" if top >= 0 else str(top)
    return f"{max(1, width)}x{max(1, height)}{x}{y}"


def _border_rectangles(rect: Rectangle, border_size: int = 5) -> tuple[Rectangle, ...]:
    """Return four thin strips; never return a monitor-sized overlay rectangle."""

    size = max(1, min(border_size, rect.width, rect.height))
    return (
        Rectangle(left=rect.left, top=rect.top, width=rect.width, height=size),
        Rectangle(left=rect.left, top=rect.bottom - size, width=rect.width, height=size),
        Rectangle(left=rect.left, top=rect.top, width=size, height=rect.height),
        Rectangle(left=rect.right - size, top=rect.top, width=size, height=rect.height),
    )


def _configure_window(window: Any) -> None:
    window.overrideredirect(True)
    window.attributes("-topmost", True)
    window.update_idletasks()
    try:
        import ctypes
        import win32con
        import win32gui

        hwnd = int(window.winfo_id())
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        ex_style |= (
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_NOACTIVATE
            | win32con.WS_EX_TOOLWINDOW
        )
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
        except Exception:
            pass
    except Exception:
        pass


def _overlay_process_main(rect_data: dict[str, int], label: str, events: Any) -> None:
    """Own all Tcl/Tk objects in a dedicated process."""

    import tkinter as tk

    rect = Rectangle(**rect_data)
    colors = {
        "ready": "#00E5FF",
        "working": "#39FF14",
        "waiting": "#FFD400",
        "error": "#FF1744",
        "question": "#D500F9",
        "stopped": "#FF1744",
    }
    root = tk.Tk()
    root.withdraw()
    windows: list[Any] = []
    borders: list[Any] = []
    border_size = 5

    def make_strip(left: int, top: int, width: int, height: int) -> Any:
        window = tk.Toplevel(root)
        window.configure(bg=colors["ready"])
        window.geometry(_geometry(width, height, left, top))
        _configure_window(window)
        windows.append(window)
        borders.append(window)
        return window

    for strip in _border_rectangles(rect, border_size):
        make_strip(strip.left, strip.top, strip.width, strip.height)

    banner_width = min(max(420, rect.width // 2), max(420, rect.width - 32))
    banner = tk.Toplevel(root)
    banner.configure(bg="#111318")
    banner.geometry(_geometry(banner_width, 42, rect.left + 16, rect.top + 14))
    banner_label = tk.Label(
        banner,
        text=f"WINDOWS AGENT · {label} · ASSIGNED",
        bg="#111318",
        fg="#FFFFFF",
        anchor="w",
        padx=12,
        font=("Segoe UI", 10, "bold"),
    )
    banner_label.pack(fill="both", expand=True)
    _configure_window(banner)
    windows.append(banner)

    cursor_size = 76
    cursor = tk.Toplevel(root)
    cursor.configure(bg="#111318")
    cursor.geometry(_geometry(cursor_size, cursor_size, rect.left + 80, rect.top + 90))
    canvas = tk.Canvas(
        cursor,
        width=cursor_size,
        height=cursor_size,
        bg="#111318",
        highlightbackground="#FF00E5",
        highlightthickness=4,
        bd=0,
    )
    canvas.pack(fill="both", expand=True)
    canvas.create_line(10, cursor_size // 2, cursor_size - 10, cursor_size // 2, fill="#00E5FF", width=3)
    canvas.create_line(cursor_size // 2, 10, cursor_size // 2, cursor_size - 10, fill="#00E5FF", width=3)
    cursor_text = canvas.create_text(
        cursor_size // 2,
        cursor_size - 12,
        text="AI",
        fill="#FFFFFF",
        font=("Segoe UI", 8, "bold"),
    )
    _configure_window(cursor)
    windows.append(cursor)
    cursor.withdraw()

    def set_state(text: str, state: str) -> None:
        color = colors.get(state, colors["ready"])
        for strip in borders:
            strip.configure(bg=color)
        banner_label.configure(text=f"WINDOWS AGENT · {label} · {text}", fg=color)

    def move_cursor(screen_x: int, screen_y: int, action: str) -> None:
        if not rect.contains(screen_x, screen_y):
            cursor.withdraw()
            return
        left = min(max(rect.left + border_size, screen_x + 16), rect.right - cursor_size - border_size)
        top = min(max(rect.top + border_size, screen_y + 16), rect.bottom - cursor_size - border_size)
        cursor.geometry(_geometry(cursor_size, cursor_size, left, top))
        canvas.itemconfigure(cursor_text, text=f"AI\n{action.upper()[:9]}")
        cursor.deiconify()
        cursor.lift()

    def shutdown() -> None:
        for window in windows:
            try:
                window.destroy()
            except Exception:
                pass
        try:
            root.destroy()
        except Exception:
            pass

    def poll() -> None:
        try:
            while True:
                event = events.get_nowait()
                kind = event.get("kind")
                payload = event.get("payload") or {}
                if kind == "stop":
                    shutdown()
                    return
                if kind == "status":
                    set_state(str(payload.get("text", "READY")), str(payload.get("state", "ready")))
                elif kind == "cursor":
                    move_cursor(int(payload.get("x", 0)), int(payload.get("y", 0)), str(payload.get("action", "action")))
        except queue.Empty:
            pass
        try:
            root.after(50, poll)
        except Exception:
            return

    root.after(50, poll)
    root.mainloop()


class AgentOverlay:
    _geometry = staticmethod(_geometry)

    def __init__(self) -> None:
        self._ctx = mp.get_context("spawn")
        self._events: Any | None = None
        self._process: mp.Process | None = None

    def start(self, rect: Rectangle, label: str) -> None:
        if self._process is not None and self._process.is_alive():
            return
        self._events = self._ctx.Queue()
        self._process = self._ctx.Process(
            target=_overlay_process_main,
            args=(rect.model_dump(), label, self._events),
            name="windows-agent-overlay",
            daemon=True,
        )
        self._process.start()

    def _send(self, kind: str, payload: dict[str, object]) -> None:
        if self._events is None or self._process is None or not self._process.is_alive():
            return
        try:
            self._events.put_nowait({"kind": kind, "payload": payload})
        except Exception:
            pass

    def status(self, text: str, state: str = "ready") -> None:
        self._send("status", {"text": text, "state": state})

    def cursor(self, x: int, y: int, action: str) -> None:
        self._send("cursor", {"x": x, "y": y, "action": action})

    def stop(self) -> None:
        process = self._process
        if process is None:
            return
        self._send("stop", {})
        process.join(timeout=1.0)
        if process.is_alive():
            process.terminate()
            process.join(timeout=0.5)
        if process.is_alive():
            process.kill()
        self._process = None
        if self._events is not None:
            try:
                self._events.close()
                self._events.join_thread()
            except Exception:
                pass
        self._events = None


def create_overlay(enabled: bool) -> Overlay:
    if not enabled or platform.system() != "Windows":
        return NullOverlay()
    return AgentOverlay()
