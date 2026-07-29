from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml


class AppLauncher:
    def __init__(self, aliases_file: Path, allow_unlisted: bool = False) -> None:
        self.aliases_file = aliases_file
        self.allow_unlisted = allow_unlisted
        self.aliases = self._load_aliases()

    def _load_aliases(self) -> dict[str, dict[str, Any]]:
        if not self.aliases_file.exists():
            return {}
        data = yaml.safe_load(self.aliases_file.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise RuntimeError(f"App aliases file must contain a mapping: {self.aliases_file}")
        return {str(name).lower(): value for name, value in data.items() if isinstance(value, dict)}

    def available_aliases(self) -> list[str]:
        return sorted(self.aliases)

    def launch(self, app_name: str) -> str:
        key = app_name.strip().lower()
        definition = self.aliases.get(key)
        if definition:
            uri = definition.get("uri")
            command = definition.get("command")
            if uri:
                os.startfile(str(uri))  # type: ignore[attr-defined]
                return f"Opened URI alias {key}: {uri}"
            if isinstance(command, list) and command:
                subprocess.Popen([str(part) for part in command], shell=False)
                return f"Launched app alias {key}: {command[0]}"
            raise RuntimeError(f"Invalid definition for app alias {key!r}")

        if not self.allow_unlisted:
            raise RuntimeError(
                f"App {app_name!r} is not in {self.aliases_file}. Add an alias or enable unlisted apps."
            )

        path = Path(app_name)
        if path.exists():
            os.startfile(str(path.resolve()))  # type: ignore[attr-defined]
            return f"Opened {path.resolve()}"

        subprocess.Popen([app_name], shell=False)
        return f"Launched unlisted executable: {app_name}"
