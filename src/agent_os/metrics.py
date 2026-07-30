from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ActionMetric:
    sequence: int
    action: str
    status: str
    ok: bool
    input_mode: str
    duration_ms: int
    changed: bool | None
    before_observation_id: str | None
    after_observation_id: str | None
    target_backend: str
    semantic: bool
    coordinate: bool
    summary: str

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


@dataclass
class RunMetrics:
    started_monotonic: float = field(default_factory=time.monotonic)
    actions: list[ActionMetric] = field(default_factory=list)

    def reset(self) -> None:
        self.started_monotonic = time.monotonic()
        self.actions.clear()

    def record(self, metric: ActionMetric) -> None:
        self.actions.append(metric)

    def summary(self) -> dict[str, object]:
        total = len(self.actions)
        successes = sum(item.status == "verified_success" for item in self.actions)
        failures = sum(item.status == "verified_failure" for item in self.actions)
        unknown = sum(item.status == "unknown_outcome" for item in self.actions)
        semantic = sum(item.semantic for item in self.actions)
        coordinates = sum(item.coordinate for item in self.actions)
        changed = sum(item.changed is True for item in self.actions)
        return {
            "elapsed_ms": round((time.monotonic() - self.started_monotonic) * 1000),
            "actions": total,
            "verified_successes": successes,
            "verified_failures": failures,
            "unknown_outcomes": unknown,
            "semantic_actions": semantic,
            "coordinate_actions": coordinates,
            "actions_with_observed_change": changed,
            "semantic_rate": round(semantic / total, 4) if total else 0.0,
            "coordinate_rate": round(coordinates / total, 4) if total else 0.0,
            "verified_success_rate": round(successes / total, 4) if total else 0.0,
        }

    def write(self, run_dir: Path, recovery: dict[str, object] | None = None) -> Path:
        path = run_dir / "metrics.json"
        payload = {
            "summary": self.summary(),
            "recovery": recovery or {},
            "actions": [item.as_dict() for item in self.actions],
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
