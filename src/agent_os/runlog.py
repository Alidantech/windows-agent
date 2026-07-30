from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SECRET_KEY = re.compile(r"(api[_-]?key|token|secret|password|authorization)", re.IGNORECASE)


def _slug(text: str, limit: int = 50) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (value or "task")[:limit]


def _redact(value: Any, key_hint: str = "") -> Any:
    if _SECRET_KEY.search(key_hint):
        return "***REDACTED***"
    if isinstance(value, dict):
        return {str(key): _redact(item, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


class RunLogger:
    def __init__(self, runs_dir: Path, task: str, target: str, model: str) -> None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_id = f"{timestamp}-{_slug(task)}"
        self.run_dir = runs_dir / self.run_id
        self.screens_dir = self.run_dir / "screens"
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.screens_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events.jsonl"
        self.text_path = self.run_dir / "agent.log"
        self.manifest_path = self.run_dir / "manifest.json"
        self._event_sequence = 0
        self._previous_event_hash = "GENESIS"
        self._write_manifest(
            {
                "run_id": self.run_id,
                "created_at": self._now(),
                "task": task,
                "target": target,
                "model": model,
                "status": "running",
                "event_log": {
                    "path": str(self.events_path),
                    "hash_chain": "sha256",
                    "genesis": self._previous_event_hash,
                },
            }
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _write_manifest(self, data: dict[str, Any]) -> None:
        self.manifest_path.write_text(
            json.dumps(_redact(data), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def update_manifest(self, **updates: Any) -> None:
        current = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        current.update(_redact(updates))
        self._write_manifest(current)

    @staticmethod
    def _event_hash(record: dict[str, Any]) -> str:
        encoded = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()

    def event(self, event_type: str, **payload: Any) -> None:
        self._event_sequence += 1
        record = {
            "sequence": self._event_sequence,
            "timestamp": self._now(),
            "type": event_type,
            "previous_hash": self._previous_event_hash,
            **_redact(payload),
        }
        record["event_hash"] = self._event_hash(record)
        self._previous_event_hash = str(record["event_hash"])
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        summary = payload.get("summary") or payload.get("message") or ""
        with self.text_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{record['timestamp']}] {event_type}: {summary}\n")
        self.update_manifest(
            event_log={
                "path": str(self.events_path),
                "hash_chain": "sha256",
                "events": self._event_sequence,
                "head": self._previous_event_hash,
            }
        )

    def screenshot_path(self, step: int, suffix: str = "before") -> Path:
        return self.screens_dir / f"step-{step:03d}-{suffix}.png"
