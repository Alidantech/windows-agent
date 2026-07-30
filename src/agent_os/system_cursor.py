from __future__ import annotations

import ctypes
import math
import platform
import time
from ctypes import wintypes


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def _user32():
    if platform.system() != "Windows":
        return None
    return ctypes.windll.user32


def position() -> tuple[int, int] | None:
    user32 = _user32()
    if user32 is None:
        return None
    point = POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        return None
    return int(point.x), int(point.y)


def move_to(x: int, y: int, *, duration_ms: int = 160) -> None:
    """Move the one shared Windows cursor using screen coordinates."""

    user32 = _user32()
    if user32 is None:
        return
    start = position() or (x, y)
    distance = math.hypot(x - start[0], y - start[1])
    frames = max(1, min(24, round(max(distance / 55, duration_ms / 14))))
    delay = max(0.0, duration_ms / 1000 / frames)
    for index in range(1, frames + 1):
        progress = index / frames
        eased = 1.0 - (1.0 - progress) ** 3
        px = round(start[0] + (x - start[0]) * eased)
        py = round(start[1] + (y - start[1]) * eased)
        if not user32.SetCursorPos(px, py):
            raise OSError("Windows refused to move the shared system cursor.")
        if index < frames and delay:
            time.sleep(delay)
