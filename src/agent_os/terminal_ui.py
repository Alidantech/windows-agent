from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.text import Text

console = Console(highlight=False)


@dataclass(frozen=True)
class UIState:
    provider_model: str
    target: str
    control_mode: str
    physical_input: str


class TerminalUI:
    """Continuous terminal feed with stable action/result relationships."""

    def banner(self, state: UIState) -> None:
        title = Text("windows-agent", style="bold cyan")
        subtitle = (
            f"model {state.provider_model}  ·  target {state.target}  ·  "
            f"{state.control_mode}/{state.physical_input}"
        )
        console.print(
            Panel(
                Text(subtitle, style="dim"),
                title=title,
                border_style="cyan",
                padding=(0, 1),
            )
        )
        console.print(
            "[dim]Ask a question or describe a computer task. "
            "Ctrl+C cancels the current task.[/dim]\n"
        )

    def thinking(self, verb: str) -> Status:
        return console.status(
            f"[magenta]✢[/magenta] {verb} [dim]· Ctrl+C to interrupt[/dim]",
            spinner="dots",
            spinner_style="magenta",
        )

    def status(self, state: UIState, current: str | None, queued: int) -> None:
        table = Table(title="Session status", box=None, show_header=False)
        table.add_column(style="dim", no_wrap=True)
        table.add_column()
        table.add_row("model", state.provider_model)
        table.add_row("target", state.target)
        table.add_row("control", state.control_mode)
        table.add_row("physical input", state.physical_input)
        table.add_row("task", current or "idle")
        table.add_row("queued", str(queued))
        console.print(table)

    def assistant(self, text: str) -> None:
        console.print(f"[cyan]⏺[/cyan] {text}")

    def route(self, kind: str, reason: str) -> None:
        style = "blue" if kind == "conversation" else "cyan"
        label = "terminal response" if kind == "conversation" else "desktop task"
        console.print(
            f"[dim]  ⎿ route[/dim] [{style}]{label}[/{style}] "
            f"[dim]· {reason}[/dim]"
        )

    def chat_response(self, text: str) -> None:
        console.print("\n[blue]⏺ assistant[/blue]")
        console.print(Markdown(text))

    def action(self, step: int, limit: int, action: str, reason: str) -> None:
        console.print(
            f"\n[cyan]⏺[/cyan] [bold]{action}[/bold] [dim]({step}/{limit})[/dim]"
        )
        console.print(f"  [dim]⎿[/dim] {reason}")

    def result(self, ok: bool, summary: str, *, label: str | None = None) -> None:
        status = label or ("OK" if ok else "FAILED")
        style = "green" if ok else "red"
        console.print(f"  [dim]⎿[/dim] [{style}]{status}[/{style}] {summary}")

    def observation(
        self,
        label: str,
        details: str,
        screenshot: Path | str | None = None,
    ) -> None:
        console.print(f"[dim]  ⎿ seeing {label} · {details}[/dim]")
        if screenshot:
            console.print(f"[dim]    screenshot {screenshot}[/dim]")

    def notice(self, text: str, style: str = "yellow") -> None:
        console.print(f"  [dim]⎿[/dim] [{style}]{text}[/{style}]")

    def model_selected(self, route: str) -> None:
        console.print(f"[magenta]⏺[/magenta] model [bold]{route}[/bold]")

    def model_fallback(self, old: str, reason: str, cooldown: int) -> None:
        console.print(
            f"[yellow]⏺[/yellow] switching from [bold]{old}[/bold] "
            "· context preserved"
        )
        console.print(f"  [dim]⎿ cooldown {cooldown}s · {reason}[/dim]")

    def complete(self, summary: str, run_dir: str | None = None) -> None:
        console.print(f"\n[green]⏺ DONE[/green] {summary}")
        if run_dir:
            console.print(f"  [dim]⎿ evidence {run_dir}[/dim]")

    def failed(self, summary: str, run_dir: str | None = None) -> None:
        console.print(f"\n[red]⏺ FAILED[/red] {summary}")
        if run_dir:
            console.print(f"  [dim]⎿ evidence {run_dir}[/dim]")

    def queue(self, current: str | None, pending: list[str]) -> None:
        table = Table(
            title="Task queue",
            box=None,
            show_header=True,
            header_style="dim",
        )
        table.add_column("State", width=10)
        table.add_column("Task")
        if current:
            table.add_row("working", current)
        for task in pending:
            table.add_row("pending", task)
        if not current and not pending:
            table.add_row("idle", "No queued tasks")
        console.print(table)

    def command_table(
        self,
        rows: list[tuple[str, str]],
        title: str = "Commands",
    ) -> None:
        table = Table(title=title, box=None, show_header=False)
        table.add_column(style="cyan", no_wrap=True)
        table.add_column(style="dim")
        for command, help_text in rows:
            table.add_row(command, help_text)
        console.print(table)


ui = TerminalUI()
