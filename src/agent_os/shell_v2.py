from __future__ import annotations

import sys

from agent_os.shell import COMMANDS, WindowsAgentShell as BaseWindowsAgentShell
from agent_os.terminal_ui import ui

COMMANDS["/set"] = "Change target, control mode, physical input, cursor or overlay"


class WindowsAgentShell(BaseWindowsAgentShell):
    """Persistent shell with explicit cursor presentation controls."""

    def _set_command(self, args: list[str]) -> None:
        if args and args[0].lower() == "cursor":
            if len(args) < 2:
                ui.notice("Use /set cursor virtual|system|off.", "red")
                return
            value = args[1].strip().lower()
            if value not in {"virtual", "system", "off"}:
                ui.notice("Cursor mode must be virtual, system, or off.", "red")
                return
            if value == "system" and self.settings.physical_input_policy == "deny":
                ui.notice(
                    "System cursor mode moves the one shared Windows cursor. "
                    "Run /set physical allow first, or keep /set cursor virtual.",
                    "yellow",
                )
                return
            self.settings.cursor_mode = value  # type: ignore[assignment]
            ui.result(True, f"Set cursor to {value}.")
            if value == "system":
                ui.notice(
                    "The agent will temporarily move your real Windows cursor while browser "
                    "actions run. Do not use the mouse at the same time.",
                    "yellow",
                )
            return
        super()._set_command(args)

    def _handle_command(self, text: str) -> bool:
        result = super()._handle_command(text)
        if text.strip().lower() == "/status":
            ui.notice(f"cursor: {self.settings.cursor_mode}", "dim")
        return result


def main() -> None:
    if len(sys.argv) > 1:
        if sys.argv[1] in {"-h", "--help"}:
            print(
                "Run `windows-agent` with no arguments, then use /help "
                "inside the persistent console."
            )
            raise SystemExit(0)
        print(
            "Windows Agent no longer accepts task/provider arguments. "
            "Run `windows-agent` and use slash commands."
        )
        raise SystemExit(2)
    raise SystemExit(WindowsAgentShell().run())
