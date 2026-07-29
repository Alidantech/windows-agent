from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agent_os.cancellation import CancellationToken


@dataclass(frozen=True)
class TaskRecord:
    task: str
    success: bool
    summary: str
    run_id: str
    timestamp: str


@dataclass
class SessionMemory:
    limit: int = 12
    records: list[TaskRecord] = field(default_factory=list)

    def add(self, task: str, success: bool, summary: str, run_id: str) -> None:
        self.records.append(
            TaskRecord(
                task=task,
                success=success,
                summary=summary,
                run_id=run_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
        del self.records[:-self.limit]

    def context(self) -> list[dict[str, object]]:
        return [record.__dict__.copy() for record in self.records]

    def clear(self) -> None:
        self.records.clear()


class QuestionBroker:
    """Route an agent question back into the persistent prompt safely."""

    def __init__(self, cancellation: CancellationToken) -> None:
        self.cancellation = cancellation
        self._lock = threading.Lock()
        self._question: str | None = None
        self._answer: queue.Queue[str] = queue.Queue(maxsize=1)

    @property
    def pending_question(self) -> str | None:
        with self._lock:
            return self._question

    def ask(self, question: str) -> str:
        while True:
            try:
                self._answer.get_nowait()
            except queue.Empty:
                break
        with self._lock:
            self._question = question
        while True:
            self.cancellation.raise_if_cancelled()
            try:
                answer = self._answer.get(timeout=0.1)
                with self._lock:
                    self._question = None
                return answer
            except queue.Empty:
                continue

    def answer(self, value: str) -> bool:
        with self._lock:
            if self._question is None:
                return False
        try:
            self._answer.put_nowait(value)
        except queue.Full:
            return False
        return True

    def cancel(self) -> None:
        with self._lock:
            was_waiting = self._question is not None
            self._question = None
        if not was_waiting:
            return
        try:
            self._answer.put_nowait("STOP")
        except queue.Full:
            pass
