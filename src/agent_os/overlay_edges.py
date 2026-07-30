from __future__ import annotations

import multiprocessing as mp
import queue
from contextlib import suppress
from typing import Any

from agent_os.models import Rectangle
from agent_os.overlay import (
    _configure_window,
    _geometry,
    _gradient_rectangles,
    _set_per_monitor_dpi_awareness,
)


def _process_main(rect_data: dict[str, int], label: str, events: Any) -> None:
    """Render only edge gradients. No cursor-shaped window is ever created."""

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

    for strip, alpha in _gradient_rectangles(rect):
        window = tk.Toplevel(root)
        window.configure(bg=colors["ready"])
        window.geometry(_geometry(strip.width, strip.height, strip.left, strip.top))
        with suppress(Exception):
            window.attributes("-alpha", alpha)
        _configure_window(window)
        windows.append(window)

    def set_state(state: str) -> None:
        color = colors.get(state, colors["ready"])
        for window in windows:
            with suppress(Exception):
                window.configure(bg=color)

    def shutdown() -> None:
        for window in windows:
            with suppress(Exception):
                window.destroy()
        with suppress(Exception):
            root.destroy()

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
                    set_state(str(payload.get("state", "ready")))
        except queue.Empty:
            pass
        with suppress(Exception):
            root.after(24, poll)

    root.after(24, poll)
    root.mainloop()


class EdgeOverlay:
    """Click-through monitor focus gradient without any pointer window."""

    def __init__(self) -> None:
        self._ctx = mp.get_context("spawn")
        self._events: Any | None = None
        self._process: mp.Process | None = None

    def start(self, rect: Rectangle, label: str) -> None:
        if self._process is not None and self._process.is_alive():
            return
        self._events = self._ctx.Queue()
        self._process = self._ctx.Process(
            target=_process_main,
            args=(rect.model_dump(), label, self._events),
            name="windows-agent-edge-overlay",
            daemon=True,
        )
        self._process.start()

    def _send(self, kind: str, payload: dict[str, object]) -> None:
        if self._events is None or self._process is None or not self._process.is_alive():
            return
        with suppress(Exception):
            self._events.put_nowait({"kind": kind, "payload": payload})

    def status(self, text: str, state: str = "ready") -> None:
        self._send("status", {"text": text, "state": state})

    def cursor(self, x: int, y: int, action: str) -> None:
        """Cursor rendering belongs to the browser page or the shared system cursor."""

        return

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
            with suppress(Exception):
                self._events.close()
                self._events.join_thread()
        self._events = None


__all__ = ["EdgeOverlay"]
