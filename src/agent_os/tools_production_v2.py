from __future__ import annotations

from urllib.parse import urlparse

from agent_os.confirmation_policy_v2 import ConfirmationPolicy
from agent_os.models import ExecutionResult
from agent_os.tools_production import ToolExecutor as BaseToolExecutor


class ToolExecutor(BaseToolExecutor):
    """Final preflight guard for observation identity and prohibited control surfaces."""

    _DENIED_DESKTOP_PROCESSES = {
        "cmd.exe",
        "powershell.exe",
        "pwsh.exe",
        "windowsterminal.exe",
        "wt.exe",
        "conhost.exe",
        "lockapp.exe",
        "logonui.exe",
        "credentialuibroker.exe",
        "securityhealthsystray.exe",
        "securityhealthservice.exe",
        "msmpeng.exe",
        "chatgpt.exe",
        "codex.exe",
    }
    _DENIED_TITLE_TERMS = (
        "windows powershell",
        "command prompt",
        "windows terminal",
        "administrator: command prompt",
        "windows security",
        "microsoft defender",
        "credential manager",
        "password manager",
        "chatgpt",
        "codex",
    )
    _DENIED_BROWSER_HOST_TERMS = (
        "1password",
        "lastpass",
        "bitwarden",
        "dashlane",
        "keepersecurity",
        "nordpass",
    )
    _WINDOW_KEY_NAMES = {
        "win",
        "windows",
        "winleft",
        "winright",
        "meta",
        "super",
        "cmd",
        "command",
        "os",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.confirmations = ConfirmationPolicy()

    @staticmethod
    def _host(url: str | None) -> str:
        if not url:
            return ""
        normalized = url if "://" in url else f"https://{url}"
        return (urlparse(normalized).hostname or "").casefold()

    def _protected_surface(self, decision, observation) -> ExecutionResult | None:
        if decision.action == "hotkey":
            keys = {str(key).strip().casefold() for key in decision.keys or []}
            if keys & self._WINDOW_KEY_NAMES:
                return ExecutionResult(
                    ok=False,
                    summary="Windows-key, Command, Meta, Super, and OS shortcuts are disabled.",
                    details={"protected_surface": "windows_key"},
                )
        if decision.action == "press_key":
            key = str(decision.key or "").strip().casefold()
            if key in self._WINDOW_KEY_NAMES:
                return ExecutionResult(
                    ok=False,
                    summary="The Windows/Meta key is disabled for UI automation.",
                    details={"protected_surface": "windows_key"},
                )

        requested_app = str(decision.app or "").strip().casefold()
        requested_window = str(decision.window or "").strip().casefold()
        if requested_app:
            executable = requested_app.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
            if executable in self._DENIED_DESKTOP_PROCESSES:
                return ExecutionResult(
                    ok=False,
                    summary=f"Automation of protected application {requested_app!r} is disabled.",
                    details={"protected_surface": "denied_application"},
                )
        if requested_window and any(
            term in requested_window for term in self._DENIED_TITLE_TERMS
        ):
            return ExecutionResult(
                ok=False,
                summary=f"Automation of protected window {decision.window!r} is disabled.",
                details={"protected_surface": "denied_window"},
            )

        if observation.target.backend == "desktop":
            target_window = next(
                (
                    item
                    for item in observation.windows
                    if item.hwnd == observation.target.hwnd
                ),
                None,
            )
            process = str(target_window.process_name or "").casefold() if target_window else ""
            title = str(target_window.title or "").casefold() if target_window else ""
            if process in self._DENIED_DESKTOP_PROCESSES or any(
                term in title for term in self._DENIED_TITLE_TERMS
            ):
                return ExecutionResult(
                    ok=False,
                    summary=(
                        "The leased target is a terminal, authentication, security, password-manager, "
                        "ChatGPT, or Codex surface that Windows Agent does not automate."
                    ),
                    details={
                        "protected_surface": "denied_desktop_target",
                        "process": process,
                        "title": title,
                    },
                )

        hostname = self._host(decision.url or observation.target.url)
        if hostname and any(term in hostname for term in self._DENIED_BROWSER_HOST_TERMS):
            return ExecutionResult(
                ok=False,
                summary=(
                    f"Automation of password-manager site {hostname!r} is disabled. "
                    "Use that site manually."
                ),
                details={
                    "protected_surface": "password_manager_site",
                    "hostname": hostname,
                },
            )
        return None

    def _domain_policy(self, decision, observation):
        if decision.action != "open_url" and observation.target.backend != "browser":
            return None
        return super()._domain_policy(decision, observation)

    def execute(self, decision, observation, lease, artifact_dir):
        if not decision.observation_id:
            return ExecutionResult(
                ok=False,
                summary=(
                    "The action is missing observation_id. Replan from the current observation and "
                    "copy its exact single-use observation ID before acting."
                ),
                details={"observation_contract": "missing_id"},
            )
        protected = self._protected_surface(decision, observation)
        if protected is not None:
            return protected
        return super().execute(decision, observation, lease, artifact_dir)


__all__ = ["ToolExecutor"]
