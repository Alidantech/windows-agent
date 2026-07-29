from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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

    @staticmethod
    def _expand_windows_vars(value: str) -> str:
        def replace(match: re.Match[str]) -> str:
            return os.environ.get(match.group(1), match.group(0))

        expanded = re.sub(r"%([^%]+)%", replace, value)
        return os.path.expandvars(os.path.expanduser(expanded))

    @staticmethod
    def _registry_app_path(executable: str) -> str | None:
        if os.name != "nt":
            return None
        try:
            import winreg
        except ImportError:
            return None

        subkey = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executable}"
        locations = (
            (winreg.HKEY_CURRENT_USER, subkey),
            (winreg.HKEY_LOCAL_MACHINE, subkey),
            (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{executable}"),
        )
        for hive, key_name in locations:
            try:
                with winreg.OpenKey(hive, key_name) as key:
                    value, _ = winreg.QueryValueEx(key, None)
                    if value and Path(str(value)).exists():
                        return str(value)
            except OSError:
                continue
        return None

    def _resolve_executable(self, executable: str, candidates: list[str] | None = None) -> str:
        expanded = self._expand_windows_vars(executable)
        direct = Path(expanded)
        if direct.is_absolute() and direct.exists():
            return str(direct)

        found = shutil.which(expanded)
        if found:
            return found

        registry_path = self._registry_app_path(Path(expanded).name)
        if registry_path:
            return registry_path

        for candidate in candidates or []:
            candidate_path = Path(self._expand_windows_vars(str(candidate)))
            if candidate_path.exists():
                return str(candidate_path)

        raise RuntimeError(
            f"Could not locate {executable!r}. Add its installed path under candidates in {self.aliases_file}."
        )

    def _command_for_alias(self, key: str, extra_args: list[str] | None = None) -> list[str]:
        definition = self.aliases.get(key)
        if not definition:
            raise RuntimeError(f"App alias {key!r} is not defined in {self.aliases_file}.")

        command = definition.get("command")
        if not isinstance(command, list) or not command:
            raise RuntimeError(f"App alias {key!r} does not define a command.")

        candidates = definition.get("candidates")
        candidate_list = [str(item) for item in candidates] if isinstance(candidates, list) else []
        executable = self._resolve_executable(str(command[0]), candidate_list)
        args = [self._expand_windows_vars(str(part)) for part in command[1:]]
        return [executable, *args, *(extra_args or [])]

    def launch(self, app_name: str) -> str:
        key = app_name.strip().lower()
        definition = self.aliases.get(key)
        if definition:
            uri = definition.get("uri")
            if uri:
                os.startfile(str(uri))  # type: ignore[attr-defined]
                return f"Opened URI alias {key}: {uri}"
            command = self._command_for_alias(key)
            subprocess.Popen(command, shell=False)
            return f"Launched app alias {key}: {command[0]}"

        if not self.allow_unlisted:
            raise RuntimeError(
                f"App {app_name!r} is not in {self.aliases_file}. Add an alias or enable unlisted apps."
            )

        path = Path(app_name)
        if path.exists():
            os.startfile(str(path.resolve()))  # type: ignore[attr-defined]
            return f"Opened {path.resolve()}"

        executable = self._resolve_executable(app_name)
        subprocess.Popen([executable], shell=False)
        return f"Launched unlisted executable: {executable}"

    def open_url(self, url: str, browser: str | None = None) -> str:
        normalized = url.strip()
        if "://" not in normalized:
            normalized = f"https://{normalized}"

        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("Only valid http:// and https:// URLs may be opened.")

        if browser:
            key = browser.strip().lower()
            command = self._command_for_alias(key, [normalized])
            subprocess.Popen(command, shell=False)
            return f"Opened {normalized} in {key}."

        os.startfile(normalized)  # type: ignore[attr-defined]
        return f"Opened {normalized} in the default browser."
