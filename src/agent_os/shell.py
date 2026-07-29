from __future__ import annotations

import importlib
import platform
import queue
import shlex
import sys
import threading
from dataclasses import dataclass

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import FuzzyWordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.table import Table

from agent_os.agent import DesktopAgent
from agent_os.cancellation import AgentCancelled
from agent_os.catalog import list_models
from agent_os.config import load_settings, parse_model_ref
from agent_os.secrets import secret_store
from agent_os.session import QuestionBroker, SessionMemory
from agent_os.terminal_ui import UIState, console, ui

COMMANDS = {
    "/help": "Show slash commands",
    "/status": "Show the active task, queue and control configuration",
    "/queue": "Show queued tasks",
    "/cancel": "Cancel the active task",
    "/models": "List live models available to configured providers",
    "/model": "Select auto or provider:model for future decisions",
    "/key": "Set, delete or inspect a provider API key safely",
    "/set": "Change target, control mode, physical input or overlay",
    "/doctor": "Validate Windows, dependencies, keys, monitors and browser",
    "/logs": "Show recent run folders",
    "/memory": "Show or clear persistent session context",
    "/clear": "Clear the terminal",
    "/exit": "Stop the agent and close the console",
}


@dataclass(frozen=True)
class TaskRequest:
    text: str


class WindowsAgentShell:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.agent = DesktopAgent(self.settings)
        self.memory = SessionMemory(self.settings.session_history_limit)
        self.questions = QuestionBroker(self.agent.cancellation)
        self.tasks: queue.Queue[TaskRequest | None] = queue.Queue()
        self._current: str | None = None
        self._shutdown = threading.Event()
        self._model_dirty = False
        self._worker = threading.Thread(
            target=self._work,
            name="windows-agent-task-worker",
            daemon=True,
        )
        history = self.settings.state_dir / "prompt-history.txt"
        self.prompt = PromptSession(
            history=FileHistory(str(history)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=FuzzyWordCompleter(list(COMMANDS), WORD=True),
            complete_while_typing=True,
        )

    @property
    def busy(self) -> bool:
        return self._current is not None

    def _state(self) -> UIState:
        route = getattr(self.agent.planner, "current_label", None) or (
            f"{self.settings.provider}:{self.settings.model}"
        )
        return UIState(
            route,
            self.settings.target,
            self.settings.control_mode,
            self.settings.physical_input_policy,
        )

    def _prompt_message(self) -> HTML:
        if self.questions.pending_question:
            return HTML("<ansigreen>answer</ansigreen> <b>❯</b> ")
        return HTML("<ansicyan>you</ansicyan> <b>❯</b> ")

    def _bottom_toolbar(self) -> HTML:
        current = "working" if self.busy else "idle"
        queued = self.tasks.qsize()
        route = getattr(self.agent.planner, "current_label", "auto")
        return HTML(
            f" <b>{current}</b> · {route} · {self.settings.target} · queue {queued} · "
            "<style fg='ansibrightblack'>/help · Ctrl+C cancel</style> "
        )

    def _invalidate(self) -> None:
        try:
            self.prompt.app.invalidate()
        except Exception:
            pass

    def enqueue(self, text: str) -> None:
        task = text.strip()
        if not task:
            return
        self.tasks.put(TaskRequest(task))
        ui.assistant(f"queued: {task}")
        self._invalidate()

    def _work(self) -> None:
        while not self._shutdown.is_set():
            request = self.tasks.get()
            if request is None:
                return
            self._current = request.text
            self._invalidate()
            try:
                outcome = self.agent.run(
                    request.text,
                    self.settings.target,
                    interactive=True,
                    ask_user=self.questions.ask,
                    session_context=self.memory.context(),
                )
                self.memory.add(request.text, outcome.success, outcome.summary, outcome.run_id)
                if outcome.success:
                    ui.complete(outcome.summary, outcome.run_dir)
                else:
                    ui.failed(outcome.summary, outcome.run_dir)
            except AgentCancelled:
                ui.notice("Task cancelled.", "yellow")
            except KeyboardInterrupt:
                ui.notice("Task cancelled.", "yellow")
            except Exception as exc:
                ui.failed(str(exc))
            finally:
                if self._model_dirty:
                    self.agent.rebuild_planner()
                    self._model_dirty = False
                self._current = None
                self.questions.cancel()
                self._invalidate()

    def cancel(self) -> None:
        if not self.busy:
            ui.notice("No task is running.", "dim")
            return
        self.agent.request_stop()
        self.questions.cancel()
        ui.notice("Cancellation requested.", "yellow")

    def _apply_model(self, value: str) -> None:
        selection = value.strip().lower()
        if selection == "auto":
            self.settings.provider = "auto"
            self.settings.model = "auto"
        else:
            provider, model = parse_model_ref(value)
            self.settings.provider = provider  # type: ignore[assignment]
            self.settings.model = model
        if self.busy:
            self._model_dirty = True
            ui.notice("Model selection saved; it will apply after the active task.")
            return
        self.agent.rebuild_planner()
        ui.model_selected(getattr(self.agent.planner, "current_label", selection))

    def _show_models(self, provider: str | None = None) -> None:
        with ui.thinking("Loading provider models…"):
            models, errors = list_models(self.settings, self.agent.prompts, provider)
        table = Table(title="Available models", box=None)
        table.add_column("Provider", style="cyan")
        table.add_column("Model")
        table.add_column("Vision")
        table.add_column("Notes", style="dim")
        for item in models:
            table.add_row(
                item.provider,
                item.model,
                "yes" if item.vision is True else "unknown",
                item.details,
            )
        console.print(table)
        for error in errors:
            ui.notice(error, "yellow")
        console.print("[dim]Select with /model auto or /model provider:model[/dim]")

    def _key_command(self, args: list[str]) -> None:
        action = args[0].lower() if args else "status"
        if action == "status":
            table = Table(title="API keys", box=None)
            table.add_column("Provider")
            table.add_column("Configured")
            table.add_column("Source", style="dim")
            for item in secret_store.statuses():
                table.add_row(item.provider, "yes" if item.configured else "no", item.source or "—")
            console.print(table)
            return
        if len(args) < 2:
            ui.notice("Use /key set PROVIDER or /key delete PROVIDER.", "red")
            return
        provider = args[1].lower()
        if action == "set":
            secret_prompt = PromptSession()
            secret = secret_prompt.prompt(
                HTML(f"<ansiyellow>{provider} API key</ansiyellow> <b>❯</b> "),
                is_password=True,
            )
            secret_store.set(provider, secret)
            ui.result(True, f"Stored {provider} key in Windows Credential Manager.")
        elif action == "delete":
            secret_store.delete(provider)
            ui.result(True, f"Deleted stored {provider} key. Environment variables are unchanged.")
        else:
            ui.notice("Unknown /key action.", "red")

    def _set_command(self, args: list[str]) -> None:
        if len(args) < 2:
            ui.notice(
                "Use /set target VALUE, /set control VALUE, /set physical VALUE or /set overlay on|off.",
                "red",
            )
            return
        key, value = args[0].lower(), " ".join(args[1:]).strip()
        if key == "target":
            self.settings.target = value
        elif key == "control" and value in {"auto", "browser", "desktop"}:
            self.settings.control_mode = value  # type: ignore[assignment]
        elif key == "physical" and value in {"deny", "ask", "allow"}:
            self.settings.physical_input_policy = value  # type: ignore[assignment]
        elif key == "overlay" and value.lower() in {"on", "off"}:
            self.settings.overlay_enabled = value.lower() == "on"
            self.agent.set_overlay(self.settings.overlay_enabled)
        else:
            ui.notice(f"Unsupported setting: {key}={value}", "red")
            return
        ui.result(True, f"Set {key} to {value}.")

    def _doctor(self) -> None:
        table = Table(title="Windows Agent doctor", box=None)
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Details", style="dim")
        table.add_row("Python", "OK", sys.version.split()[0])
        table.add_row("Platform", "OK" if platform.system() == "Windows" else "FAILED", platform.platform())
        for module in (
            "prompt_toolkit", "rich", "keyring", "playwright.sync_api", "mss", "pywinauto", "win32gui",
        ):
            try:
                importlib.import_module(module)
                table.add_row(module, "OK", "available")
            except Exception as exc:
                table.add_row(module, "FAILED", str(exc))
        for status in secret_store.statuses():
            table.add_row(
                f"{status.provider} key",
                "OK" if status.configured else "MISSING",
                status.source or "use /key set",
            )
        try:
            monitors = self.agent.capture.list_monitors()
            table.add_row("Monitors", "OK", f"detected {len(monitors)}")
        except Exception as exc:
            table.add_row("Monitors", "FAILED", str(exc))
        console.print(table)

    def _logs(self) -> None:
        paths = sorted(self.settings.runs_dir.glob("*"), reverse=True)[:10]
        if not paths:
            ui.notice("No runs recorded yet.", "dim")
            return
        for path in paths:
            console.print(f"[dim]⎿[/dim] {path}")

    def _handle_command(self, text: str) -> bool:
        try:
            parts = shlex.split(text)
        except ValueError as exc:
            ui.notice(str(exc), "red")
            return True
        command = parts[0].lower()
        args = parts[1:]
        if command == "/help":
            ui.command_table(list(COMMANDS.items()))
        elif command == "/status":
            ui.status(self._state(), self._current, self.tasks.qsize())
            ui.queue(self._current, [item.text for item in list(self.tasks.queue) if item is not None])
        elif command == "/queue":
            ui.queue(self._current, [item.text for item in list(self.tasks.queue) if item is not None])
        elif command == "/cancel":
            self.cancel()
        elif command == "/models":
            self._show_models(args[0].lower() if args else None)
        elif command == "/model":
            if not args:
                current = getattr(self.agent.planner, "current_label", "auto")
                ui.notice(f"Current model: {current}", "cyan")
            else:
                self._apply_model(args[0])
        elif command == "/key":
            self._key_command(args)
        elif command == "/set":
            self._set_command(args)
        elif command == "/doctor":
            self._doctor()
        elif command == "/logs":
            self._logs()
        elif command == "/memory":
            if args and args[0] == "clear":
                self.memory.clear()
                ui.result(True, "Session memory cleared.")
            else:
                for item in self.memory.context():
                    console.print(f"[dim]⎿[/dim] {item['task']} → {item['summary']}")
        elif command == "/clear":
            console.clear()
            ui.banner(self._state())
        elif command in {"/exit", "/quit"}:
            return False
        else:
            ui.notice(f"Unknown command {command}. Use /help.", "red")
        return True

    def handle_command(self, text: str) -> bool:
        try:
            return self._handle_command(text)
        except AgentCancelled:
            ui.notice("Command cancelled.", "yellow")
        except KeyboardInterrupt:
            ui.notice("Command cancelled.", "yellow")
        except Exception as exc:
            ui.notice(f"Command failed: {exc}", "red")
        return True

    def run(self) -> int:
        if platform.system() != "Windows":
            console.print("[red]Windows Agent must run on Windows.[/red]")
            return 2
        ui.banner(self._state())
        self._worker.start()
        running = True
        with patch_stdout(raw=True):
            while running:
                try:
                    text = self.prompt.prompt(
                        self._prompt_message(),
                        bottom_toolbar=self._bottom_toolbar(),
                    )
                except KeyboardInterrupt:
                    if self.busy:
                        self.cancel()
                        continue
                    ui.notice("Use /exit to close. Ctrl+C cancels only an active task.", "dim")
                    continue
                except EOFError:
                    break
                if self.questions.pending_question:
                    if not self.questions.answer(text):
                        ui.notice("The question is no longer pending.", "yellow")
                    continue
                stripped = text.strip()
                if not stripped:
                    continue
                if stripped.startswith("/"):
                    running = self.handle_command(stripped)
                else:
                    self.enqueue(stripped)
        self._shutdown.set()
        self.agent.request_stop()
        self.tasks.put(None)
        self._worker.join(timeout=3)
        self.agent.close(force=self._worker.is_alive())
        return 0


def main() -> None:
    if len(sys.argv) > 1:
        if sys.argv[1] in {"-h", "--help"}:
            print("Run `windows-agent` with no arguments, then use /help inside the persistent console.")
            raise SystemExit(0)
        print(
            "Windows Agent no longer accepts task/provider arguments. "
            "Run `windows-agent` and use slash commands."
        )
        raise SystemExit(2)
    raise SystemExit(WindowsAgentShell().run())
