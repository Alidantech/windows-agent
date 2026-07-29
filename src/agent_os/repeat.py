from __future__ import annotations

from collections import deque


class RepeatDetector:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._signatures: deque[str] = deque(maxlen=limit)

    def add(self, signature: str) -> int:
        self._signatures.append(signature)
        count = 0
        for value in reversed(self._signatures):
            if value == signature:
                count += 1
            else:
                break
        return count

    def clear(self) -> None:
        self._signatures.clear()
