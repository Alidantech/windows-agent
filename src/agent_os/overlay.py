from __future__ import annotations

import platform
import queue
import threading
from dataclasses import dataclass
from typing import Protocol

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


class AgentOverlay:
    def __init__(self) -> None:
        self._events: queue.Queue[OverlayEvent] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self, rect: Rectangle, label: str) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            args=(rect, label),
            name="agent-os-overlay",
            daemon=True,
        )
        self._thread.start()

    def status(self, text: str, state: str = "ready") -> None:
        self._events.put(OverlayEvent("status", {"text": text, "state": state}))

    def cursor(self, x: int, y: int, action: str) -> None:
        self._events.put(OverlayEvent("cursor", {"x": x, "y": y, "action": action}))

    def stop(self) -> None:
        self._events.put(OverlayEvent("stop", {}))
        if self._thread:
            self._thread.join(timeout=1.5)
            self._thread = None

    def _run(self, rect: Rectangle, label: str) -> None:
        import tkinter as tk

        transparent = "#010101"
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=transparent)
        try:
            root.wm_attributes("-transparentcolor", transparent)
        except tk.TclError:
            pass
        root.geometry(f"{rect.width}x{rect.height}+{rect.left}+{rect.top}")

        canvas = tk.Canvas(
            root,
            width=rect.width,
            height=rect.height,
            bg=transparent,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(fill="both", expand=True)
        colors = {
            "ready": "#00E5FF",
            "working": "#39FF14",
            "waiting": "#FFD400",
            "error": "#FF1744",
            "question": "#D500F9",
        }
        border = canvas.create_rectangle(
            4,
            4,
            rect.width - 5,
            rect.height - 5,
            outline=colors["ready"],
            width=7,
        )
        banner = canvas.create_rectangle(16, 16, min(rect.width - 16, 880), 62, fill="#101010", outline="")
        text = canvas.create_text(
            30,
            39,
            text=f"AGENT OS · {label}",
            fill="#FFFFFF",
            anchor="w",
            font=("Segoe UI", 14, "bold"),
        )
        cursor_items: list[int] = []

        try:
            import ctypes
            import win32con
            import win32gui

            root.update_idletasks()
            hwnd = int(root.winfo_id())
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            ex_style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
            try:
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
            except Exception:
                pass
        except Exception:
            pass

        def draw_cursor(screen_x: int, screen_y: int, action: str) -> None:
            for item in cursor_items:
                canvas.delete(item)
            cursor_items.clear()
            x = screen_x - rect.left
            y = screen_y - rect.top
            if not (0 <= x < rect.width and 0 <= y < rect.height):
                return
            cursor_items.extend(
                [
                    canvas.create_oval(x - 20, y - 20, x + 20, y + 20, outline="#FF00E5", width=5),
                    canvas.create_line(x - 34, y, x + 34, y, fill="#00E5FF", width=3),
                    canvas.create_line(x, y - 34, x, y + 34, fill="#00E5FF", width=3),
                    canvas.create_text(
                        x + 26,
                        y - 24,
                        text=f"AI {action.upper()}",
                        fill="#FFFFFF",
                        anchor="sw",
                        font=("Segoe UI", 11, "bold"),
                    ),
                ]
            )

        def poll() -> None:
            try:
                while True:
                    event = self._events.get_nowait()
                    if event.kind == "stop":
                        root.destroy()
                        return
                    if event.kind == "status":
                        state = str(event.payload.get("state", "ready"))
                        canvas.itemconfigure(border, outline=colors.get(state, colors["ready"]))
                        canvas.itemconfigure(banner, fill="#101010")
                        canvas.itemconfigure(text, text=f"AGENT OS · {label} · {event.payload.get('text', '')}")
                    elif event.kind == "cursor":
                        draw_cursor(
                            int(event.payload.get("x", 0)),
                            int(event.payload.get("y", 0)),
                            str(event.payload.get("action", "action")),
                        )
            except queue.Empty:
                pass
            if root.winfo_exists():
                root.after(50, poll)

        root.after(50, poll)
        root.mainloop()


def create_overlay(enabled: bool) -> Overlay:
    if not enabled or platform.system() != "Windows":
        return NullOverlay()
    return AgentOverlay()
