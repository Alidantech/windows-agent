from __future__ import annotations

import math
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class CursorActivity:
    moving: bool
    start: tuple[int, int]
    end: tuple[int, int]
    distance: float


class UserActivityGuard:
    @staticmethod
    def cursor_position() -> tuple[int, int]:
        try:
            import win32api

            x, y = win32api.GetCursorPos()
            return int(x), int(y)
        except Exception:
            return (0, 0)

    def sample(self, seconds: float = 0.22, threshold: float = 5.0) -> CursorActivity:
        start = self.cursor_position()
        time.sleep(max(0.0, seconds))
        end = self.cursor_position()
        distance = math.dist(start, end)
        return CursorActivity(distance >= threshold, start, end, distance)
