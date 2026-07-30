from __future__ import annotations

import math
import multiprocessing as mp
import queue
from typing import Any

from agent_os.models import Rectangle
from agent_os.overlay import (
    _configure_window,
    _geometry,
    _gradient_rectangles,
    _set_per_monitor_dpi_awareness,
)


def _hand_rgba(size: int, accent: str, pulse: int = 0):
    """Render a transparent, emoji-like pointing hand without relying on color fonts."""

    from PIL import Image, ImageColor, ImageDraw

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    skin = (255, 214, 170, 255)
    shade = (224, 166, 113, 255)
    outline = (73, 45, 28, 255)
    glow = ImageColor.getrgb(accent) + (220,)

    if pulse:
        radius = 25 + pulse * 3
        alpha = max(0, 190 - pulse * 24)
        pulse_color = glow[:3] + (alpha,)
        center = (size // 2, size // 2)
        draw.ellipse(
            (
                center[0] - radius,
                center[1] - radius,
                center[0] + radius,
                center[1] + radius,
            ),
            outline=pulse_color,
            width=max(1, 4 - pulse // 3),
        )

    draw.rounded_rectangle((27, 24, 56, 64), radius=12, fill=(0, 0, 0, 80))
    draw.rounded_rectangle((26, 2, 43, 47), radius=8, fill=(0, 0, 0, 80))
    draw.rounded_rectangle((23, 0, 43, 47), radius=9, fill=skin, outline=outline, width=2)
    draw.rounded_rectangle((20, 31, 57, 68), radius=13, fill=skin, outline=outline, width=2)
    for box in ((38, 28, 57, 43), (39, 39, 59, 53), (35, 50, 55, 64)):
        draw.rounded_rectangle(box, radius=7, fill=skin, outline=outline, width=2)
    draw.polygon(
        [(21, 37), (10, 31), (5, 37), (18, 53), (29, 50)],
        fill=skin,
        outline=outline,
    )
    draw.line([(11, 37), (22, 48)], fill=shade, width=2)
    draw.line([(27, 15), (39, 15)], fill=shade, width=2)
    draw.ellipse((27, 4, 39, 16), outline=glow, width=3)
    return image


def _process_main(rect_data: dict[str, int], label: str, events: Any) -> None:
    _set_per_monitor_dpi_awareness()
    import tkinter as tk

    from PIL import ImageTk

    rect = Rectangle(**rect_data)
    colors = {
        "ready": "#00E5FF",
        "working": "#39FF14",
        "waiting": "#FFD400",
        "error": "#FF1744",
        "question": "#D500F9",
        "stopped": "#FF1744",
    }
    state_color = colors["ready"]
    root = tk.Tk()
    root.withdraw()
    windows: list[Any] = []
    gradients: list[Any] = []

    for strip, alpha in _gradient_rectangles(rect):
        window = tk.Toplevel(root)
        window.configure(bg=state_color)
        window.geometry(_geometry(strip.width, strip.height, strip.left, strip.top))
        window.attributes("-alpha", alpha)
        _configure_window(window)
        windows.append(window)
        gradients.append(window)

    size = 78
    hotspot_x = 33
    hotspot_y = 7
    chroma = "#FF00FF"
    cursor = tk.Toplevel(root)
    cursor.configure(bg=chroma)
    cursor.geometry(
        _geometry(
            size,
            size,
            rect.left + rect.width // 2 - hotspot_x,
            rect.top + rect.height // 2 - hotspot_y,
        )
    )
    cursor.attributes("-transparentcolor", chroma)
    _configure_window(cursor)
    label_widget = tk.Label(cursor, bg=chroma, bd=0, highlightthickness=0)
    label_widget.pack(fill="both", expand=True)
    windows.append(cursor)
    cursor.withdraw()

    current_x = rect.left + rect.width // 2
    current_y = rect.top + rect.height // 2
    animation_id = 0
    photo: Any | None = None

    def render(pulse: int = 0) -> None:
        nonlocal photo
        photo = ImageTk.PhotoImage(_hand_rgba(size, state_color, pulse), master=cursor)
        label_widget.configure(image=photo)

    render()

    def set_state(_text: str, state: str) -> None:
        nonlocal state_color
        state_color = colors.get(state, colors["ready"])
        for strip in gradients:
            strip.configure(bg=state_color)
        render()

    def place(screen_x: int, screen_y: int) -> None:
        left = min(max(rect.left, screen_x - hotspot_x), rect.right - size)
        top = min(max(rect.top, screen_y - hotspot_y), rect.bottom - size)
        cursor.geometry(_geometry(size, size, left, top))
        cursor.deiconify()
        cursor.lift()

    def pulse(token: int, frame: int = 1) -> None:
        if token != animation_id:
            return
        if frame > 7:
            render()
            return
        render(frame)
        root.after(28, lambda: pulse(token, frame + 1))

    def animate(screen_x: int, screen_y: int, action: str) -> None:
        nonlocal current_x, current_y, animation_id
        if not rect.contains(screen_x, screen_y):
            cursor.withdraw()
            return
        animation_id += 1
        token = animation_id
        start_x, start_y = current_x, current_y
        distance = math.hypot(screen_x - start_x, screen_y - start_y)
        frames = max(4, min(24, round(distance / 50)))

        def frame(index: int) -> None:
            nonlocal current_x, current_y
            if token != animation_id:
                return
            progress = index / frames
            eased = 1.0 - (1.0 - progress) ** 3
            current_x = round(start_x + (screen_x - start_x) * eased)
            current_y = round(start_y + (screen_y - start_y) * eased)
            place(current_x, current_y)
            if index < frames:
                root.after(14, lambda: frame(index + 1))
            elif "click" in action.lower():
                pulse(token)

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
                    animate(
                        int(payload.get("x", 0)),
                        int(payload.get("y", 0)),
                        str(payload.get("action", "move")),
                    )
        except queue.Empty:
            pass
        try:
            root.after(14, poll)
        except Exception:
            return

    root.after(14, poll)
    root.mainloop()


class HandOverlay:
    """Edge focus plus an independent transparent hand cursor."""

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
            name="windows-agent-hand-overlay",
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
