from __future__ import annotations

import platform
import sys

from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout

from agent_os.shell_v2 import WindowsAgentShell as BaseWindowsAgentShell
from agent_os.terminal_ui import console, ui


def parse_submission(text: str) -> tuple[str, list[str]]:
    """Classify pasted input without splitting ordinary multiline task descriptions."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    if not lines:
        return "empty", []
    if len(lines) == 1:
        return "single", lines
    if any(line.startswith("/") for line in lines):
        return "entries", lines
    return "task", [normalized.strip()]


def create_input_bindings() -> KeyBindings:
    """Submit with Enter while allowing pasted newlines and Alt+Enter editing."""

    bindings = KeyBindings()

    @bindings.add("enter")
    def accept_input(event) -> None:
        event.current_buffer.validate_and_handle()

    @bindings.add("escape", "enter")
    def insert_newline(event) -> None:
        event.current_buffer.insert_text("\n")

    return bindings


class WindowsAgentShell(BaseWindowsAgentShell):
    """Persistent shell with safe multiline paste dispatch."""

    def __init__(self) -> None:
        super().__init__()
        self._input_bindings = create_input_bindings()

    def dispatch_submission(self, text: str) -> bool:
        mode, entries = parse_submission(text)
        if mode == "empty":
            return True
        if mode == "entries":
            ui.notice(f"Processing {len(entries)} pasted entries.", "dim")
        for entry in entries:
            if entry.startswith("/"):
                if not self.handle_command(entry):
                    return False
            else:
                self.enqueue(entry)
        return True

    def run(self) -> int:
        if platform.system() != "Windows":
            console.print("[red]Windows Agent must run on Windows.[/red]")
            return 2
        ui.banner(self._state())
        self._worker.start()
        running = True
        password_filter = Condition(lambda: self.questions.pending_sensitive)
        with patch_stdout(raw=True):
            while running:
                try:
                    text = self.prompt.prompt(
                        self._prompt_message,
                        bottom_toolbar=self._bottom_toolbar,
                        is_password=password_filter,
                        multiline=True,
                        key_bindings=self._input_bindings,
                        prompt_continuation=HTML(
                            "<ansibrightblack>  · </ansibrightblack>"
                        ),
                    )
                except KeyboardInterrupt:
                    if self.busy:
                        self.cancel()
                        continue
                    ui.notice(
                        "Use /exit to close. Ctrl+C cancels only an active task.",
                        "dim",
                    )
                    continue
                except EOFError:
                    break
                if self.questions.pending_question:
                    if not self.questions.answer(text):
                        ui.notice("The question is no longer pending.", "yellow")
                    continue
                running = self.dispatch_submission(text)
        self._shutdown.set()
        self.agent.request_stop()
        self.tasks.put(None)
        self._worker.join(timeout=3)
        self.agent.close(force=self._worker.is_alive())
        return 0


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


__all__ = ["WindowsAgentShell", "create_input_bindings", "parse_submission"]
