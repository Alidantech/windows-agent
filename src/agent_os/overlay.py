from __future__ import annotations

import math
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


def _gradient_rectangles(
    rect: Rectangle,
    *,
    depth: int = 28,
    layers: int = 10,
) -> tuple[tuple[Rectangle, float], ...]:
    """Create small edge-only strips; the monitor center never has an overlay window."""

    safe_depth = max(4, min(depth, rect.width // 3, rect.height // 3))
    count = max(2, min(layers, safe_depth))
    boundaries = [round(index * safe_depth / count) for index in range(count + 1)]
    output: list[tuple[Rectangle, float]] = []
    for index in range(count):
        offset = boundaries[index]
        thickness = max(1, boundaries[index + 1] - boundaries[index])
        progress = index / max(1, count - 1)
        alpha = 0.34 * ((1.0 - progress) ** 1.7) + 0.012
        output.extend(
            (
                (
                    Rectangle(
                        left=rect.left + offset,
                        top=rect.top + offset,
                        width=max(1, rect.width - offset * 2),
                        height=thickness,
                    ),
                    alpha,
                ),
                (
                    Rectangle(
                        left=rect.left + offset,
                        top=rect.bottom - offset - thickness,
                        width=max(1, rect.width - offset * 2),
                        height=thickness,
                    ),
                    alpha,
                ),
                (
                    Rectangle(
                        left=rect.left + offset,
                        top=rect.top + offset,
                        width=thickness,
                        height=max(1, rect.height - offset * 2),
                    ),
                    alpha,
                ),
                (
                    Rectangle(
                        left=rect.right - offset - thickness,
                        top=rect.top + offset,
                        width=thickness,
                        height=max(1, rect.height - offset * 2),
                    ),
                    alpha,
                ),
            )
        )
    return tuple(output)


def _set_per_monitor_dpi_awareness() -> None:
    try:
        import ctypes

        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass


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
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOACTIVATE
            | win32con.SWP_SHOWWINDOW,
        )
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
        except Exception:
            pass
    except Exception:
        pass


def _overlay_process_main(rect_data: dict[str, int], label: str, events: Any) -> None:
    """Own every overlay object in one DPI-aware process."""

    _set_per_monitor_dpi_awareness()
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
    gradient_windows: list[Any] = []

    for strip, alpha in _gradient_rectangles(rect):
        window = tk.Toplevel(root)
        window.configure(bg=colors["ready"])
        window.geometry(_geometry(strip.width, strip.height, strip.left, strip.top))
        try:
            window.attributes("-alpha", alpha)
        except Exception:
            pass
        _configure_window(window)
        windows.append(window)
        gradient_windows.append(window)

    cursor_size = 64
    hotspot_x = 8
    hotspot_y = 7
    chroma = "#010203"
    cursor = tk.Toplevel(root)
    cursor.configure(bg=chroma)
    cursor.geometry(
        _geometry(
            cursor_size,
            cursor_size,
            rect.left + rect.width // 2 - hotspot_x,
            rect.top + rect.height // 2 - hotspot_y,
        )
    )
    try:
        cursor.attributes("-transparentcolor", chroma)
        cursor.attributes("-alpha", 0.96)
    except Exception:
        pass
    canvas = tk.Canvas(
        cursor,
        width=cursor_size,
        height=cursor_size,
        bg=chroma,
        highlightthickness=0,
        bd=0,
    )
    canvas.pack(fill="both", expand=True)
    canvas.create_polygon(
        7, 5, 7, 37, 15, 29, 22, 47, 29, 44, 22, 27, 35, 26,
        fill="#07110A", outline="#07110A", width=3,
    )
    pointer = canvas.create_polygon(
        5, 3, 5, 34, 13, 26, 20, 44, 27, 41, 20, 24, 33, 23,
        fill=colors["working"], outline="#FFFFFF", width=2,
    )
    dot = canvas.create_oval(
        2, 1, 12, 11, fill="#FFFFFF", outline=colors["working"], width=2
    )
    ring = canvas.create_oval(
        5, 4, 11, 10, outline=colors["working"], width=3, state="hidden"
    )
    _configure_window(cursor)
    windows.append(cursor)
    cursor.withdraw()

    current_x = rect.left + rect.width // 2
    current_y = rect.top + rect.height // 2
    animation_id = 0

    def set_state(_text: str, state: str) -> None:
        color = colors.get(state, colors["ready"])
        for strip in gradient_windows:
            strip.configure(bg=color)
        canvas.itemconfigure(pointer, fill=color)
        canvas.itemconfigure(dot, outline=color)
        canvas.itemconfigure(ring, outline=color)

    def place_cursor(screen_x: int, screen_y: int) -> None:
        left = min(max(rect.left, screen_x - hotspot_x), rect.right - cursor_size)
        top = min(max(rect.top, screen_y - hotspot_y), rect.bottom - cursor_size)
        cursor.geometry(_geometry(cursor_size, cursor_size, left, top))
        cursor.deiconify()
        cursor.lift()

    def pulse_click(token: int, frame: int = 0) -> None:
        if token != animation_id:
            return
        if frame >= 12:
            canvas.itemconfigure(ring, state="hidden")
            return
        radius = 4 + frame * 2
        canvas.coords(
            ring,
            hotspot_x - radius,
            hotspot_y - radius,
            hotspot_x + radius,
            hotspot_y + radius,
        )
        canvas.itemconfigure(ring, state="normal", width=max(1, 4 - frame // 4))
        root.after(22, lambda: pulse_click(token, frame + 1))

    def animate_cursor(screen_x: int, screen_y: int, action: str) -> None:
        nonlocal current_x, current_y, animation_id
        if not rect.contains(screen_x, screen_y):
            cursor.withdraw()
            return
        animation_id += 1
        token = animation_id
        start_x, start_y = current_x, current_y
        distance = math.hypot(screen_x - start_x, screen_y - start_y)
        frames = max(4, min(22, round(distance / 55)))

        def frame(index: int) -> None:
            nonlocal current_x, current_y
            if token != animation_id:
                return
            progress = index / frames
            eased = 1.0 - (1.0 - progress) ** 3
            current_x = round(start_x + (screen_x - start_x) * eased)
            current_y = round(start_y + (screen_y - start_y) * eased)
            place_cursor(current_x, current_y)
            if index < frames:
                root.after(16, lambda: frame(index + 1))
                return
            current_x, current_y = screen_x, screen_y
            if "click" in action.lower():
                pulse_click(token)

        frame(1)

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
                    set_state(
                        str(payload.get("text", "READY")),
                        str(payload.get("state", "ready")),
                    )
                elif kind == "cursor":
                    animate_cursor(
                        int(payload.get("x", 0)),
                        int(payload.get("y", 0)),
                        str(payload.get("action", "move")),
                    )
        except queue.Empty:
            pass
        try:
            root.after(16, poll)
        except Exception:
            return

    root.after(16, poll)
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
