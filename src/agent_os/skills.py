from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    triggers: tuple[str, ...]
    body: str
    path: Path


class SkillLoader:
    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir

    @staticmethod
    def _parse(path: Path) -> Skill:
        text = path.read_text(encoding="utf-8")
        metadata: dict[str, object] = {}
        body = text
        if text.startswith("---\n"):
            _, header, body = text.split("---\n", 2)
            metadata = yaml.safe_load(header) or {}
        triggers_raw = metadata.get("triggers", [])
        triggers = tuple(str(item).lower() for item in triggers_raw) if isinstance(triggers_raw, list) else ()
        return Skill(
            name=str(metadata.get("name") or path.stem),
            description=str(metadata.get("description") or ""),
            triggers=triggers,
            body=body.strip(),
            path=path,
        )

    def all(self) -> list[Skill]:
        if not self.skills_dir.exists():
            return []
        return [self._parse(path) for path in sorted(self.skills_dir.glob("*.md"))]

    def select(self, task: str, limit: int = 5) -> list[Skill]:
        task_lower = task.lower()
        words = set(re.findall(r"[a-z0-9]+", task_lower))
        scored: list[tuple[int, Skill]] = []
        for skill in self.all():
            score = 0
            if skill.name.lower() in {"core", "safety"}:
                score += 100
            for trigger in skill.triggers:
                if trigger in task_lower:
                    score += 20
                trigger_words = set(re.findall(r"[a-z0-9]+", trigger))
                score += len(words & trigger_words)
            scored.append((score, skill))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [skill for score, skill in scored if score > 0][:limit]
