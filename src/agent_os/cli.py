from __future__ import annotations

import importlib
import json
import platform
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from agent_os.agent import DesktopAgent
from agent_os.apps import AppLauncher
from agent_os.capture import ScreenCapture
from agent_os.config import gemini_api_key, load_settings
from agent_os.windows import WindowManager

app = typer.Typer(
    name="agent-os",
    help="Supervised Gemini-powered Windows desktop automation.",
    no_args_is_help=True,
)
console = Console()


def _require_windows() -> None:
    if platform.system() != "Windows":
        raise typer.BadParameter("This project controls the Windows desktop and must run on Windows.")


def _project_path(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


@app.command()
def doctor() -> None:
    """Validate Python, packages, API configuration, monitors, and Windows access."""
    _require_windows()
    settings = load_settings()
    table = Table(title="Agent OS Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row("Python", "OK", sys.version.split()[0])
    table.add_row("Platform", "OK", platform.platform())

    modules = [
        "google.genai",
        "mss",
        "PIL",
        "pyautogui",
        "pywinauto",
        "win32gui",
        "pydantic",
        "rich",
        "typer",
    ]
    for module in modules:
        try:
            importlib.import_module(module)
            table.add_row(f"Import {module}", "OK", "available")
        except Exception as exc:
            table.add_row(f"Import {module}", "FAILED", str(exc))

    try:
        key = gemini_api_key()
        table.add_row("Gemini key", "OK", f"configured ({len(key)} characters; hidden)")
    except Exception as exc:
        table.add_row("Gemini key", "FAILED", str(exc))

    try:
        capture = ScreenCapture(settings)
        monitors = capture.list_monitors()
        table.add_row("Monitors", "OK", f"detected {len(monitors)}")
    except Exception as exc:
        table.add_row("Monitors", "FAILED", str(exc))

    try:
        windows = WindowManager().list_windows(limit=10)
        table.add_row("Visible windows", "OK", f"detected at least {len(windows)}")
    except Exception as exc:
        table.add_row("Visible windows", "FAILED", str(exc))

    apps = AppLauncher(settings.app_aliases_file, settings.allow_unlisted_apps)
    table.add_row("App aliases", "OK", ", ".join(apps.available_aliases()))
    table.add_row("Model", "OK", settings.model)
    console.print(table)


@app.command("screens")
def screens_command() -> None:
    """List monitors and visible top-level windows for target selection."""
    _require_windows()
    settings = load_settings()
    capture = ScreenCapture(settings)
    windows = WindowManager()

    monitor_table = Table(title="Monitors")
    monitor_table.add_column("Target")
    monitor_table.add_column("Left")
    monitor_table.add_column("Top")
    monitor_table.add_column("Size")
    for monitor in capture.list_monitors():
        monitor_table.add_row(
            f"monitor:{monitor.index}",
            str(monitor.rect.left),
            str(monitor.rect.top),
            f"{monitor.rect.width}x{monitor.rect.height}",
        )
    console.print(monitor_table)

    window_table = Table(title="Visible Windows")
    window_table.add_column("Active")
    window_table.add_column("Title")
    window_table.add_column("Process")
    window_table.add_column("Suggested target")
    for window in windows.list_windows(limit=60):
        window_table.add_row(
            "*" if window.active else "",
            window.title,
            window.process_name or "",
            f"window:{window.title}",
        )
    console.print(window_table)


@app.command()
def capture(
    target: str | None = typer.Option(None, help="active-window, monitor:N, desktop, or window:TITLE"),
    output: Path = typer.Option(Path("capture.png"), help="PNG output path"),
) -> None:
    """Capture and save exactly what the agent would see."""
    _require_windows()
    settings = load_settings()
    chosen_target = target or settings.target
    output = _project_path(output)
    observation = ScreenCapture(settings).capture(chosen_target, screenshot_path=output)
    console.print(f"Saved [bold]{observation.target.label}[/bold] to [cyan]{output}[/cyan]")
    console.print(
        f"Captured {observation.original_image.width}x{observation.original_image.height}; "
        f"UIA elements: {len(observation.uia.elements)}"
    )


@app.command("inspect")
def inspect_screen(
    target: str | None = typer.Option(None, help="Screen/window target"),
    output: Path = typer.Option(Path("screen-inspection.json"), help="JSON output path"),
) -> None:
    """Export the screenshot target, monitors, windows, and UI Automation elements."""
    _require_windows()
    settings = load_settings()
    chosen_target = target or settings.target
    output = _project_path(output)
    screenshot_path = output.with_suffix(".png")
    observation = ScreenCapture(settings).capture(
        chosen_target,
        screenshot_path=screenshot_path,
    )
    data = {
        "target": observation.target.model_dump(),
        "monitors": [item.model_dump() for item in observation.monitors],
        "visible_windows": [item.model_dump() for item in observation.windows],
        "ui_elements": [item.model_dump() for item in observation.uia.elements],
        "screenshot": str(screenshot_path),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"Inspection JSON: [cyan]{output}[/cyan]")
    console.print(f"Inspection screenshot: [cyan]{screenshot_path}[/cyan]")
    console.print(f"UI elements: {len(observation.uia.elements)}")


@app.command()
def run(
    task: str = typer.Argument(..., help="Natural-language desktop task"),
    target: str | None = typer.Option(None, help="Screen/window target"),
    max_steps: int | None = typer.Option(None, min=1, max=200),
    dry_run: bool = typer.Option(False, help="Plan and log actions without executing them"),
    yes: bool = typer.Option(False, "--yes", help="Auto-confirm locally classified risky actions"),
    non_interactive: bool = typer.Option(False, help="Stop instead of asking for guidance"),
) -> None:
    """Run one supervised desktop task."""
    _require_windows()
    settings = load_settings()
    chosen_target = target or settings.target
    try:
        outcome = DesktopAgent(settings, dry_run=dry_run, auto_confirm=yes).run(
            task=task,
            target_spec=chosen_target,
            max_steps=max_steps,
            interactive=not non_interactive,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped with Ctrl+C.[/yellow]")
        raise typer.Exit(code=130) from None
    except Exception as exc:
        try:
            import pyautogui

            if isinstance(exc, pyautogui.FailSafeException):
                console.print("\n[yellow]Emergency stop triggered at the top-left corner.[/yellow]")
                raise typer.Exit(code=130) from None
        except ImportError:
            pass
        console.print(f"[red]Agent failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    status = "green" if outcome.success else "red"
    console.print(f"\n[{status}]{outcome.summary}[/{status}]")
    console.print(f"Logs and screenshots: [cyan]{outcome.run_dir}[/cyan]")
    raise typer.Exit(code=0 if outcome.success else 2)


@app.command()
def chat(
    target: str | None = typer.Option(None, help="Default screen/window target"),
    dry_run: bool = typer.Option(False),
) -> None:
    """Interactive task console: keep assigning new tasks to the agent."""
    _require_windows()
    settings = load_settings()
    chosen_target = target or settings.target
    console.print("[bold cyan]Agent OS interactive console[/bold cyan]")
    console.print("Enter one task at a time. Type EXIT to close.\n")

    while True:
        try:
            task = Prompt.ask("Task").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Interactive console closed.[/yellow]")
            return
        if task.upper() in {"EXIT", "QUIT"}:
            return
        if not task:
            continue
        try:
            outcome = DesktopAgent(settings, dry_run=dry_run).run(
                task,
                target_spec=chosen_target,
                interactive=True,
            )
            console.print(f"Result: {outcome.summary}")
            console.print(f"Run: {outcome.run_dir}\n")
        except KeyboardInterrupt:
            console.print("\n[yellow]Current task stopped. Interactive console remains open.[/yellow]")
        except Exception as exc:
            console.print(f"[red]Task failed:[/red] {exc}\n")


@app.command()
def apps() -> None:
    """Show app aliases that the agent is allowed to launch."""
    settings = load_settings()
    launcher = AppLauncher(settings.app_aliases_file, settings.allow_unlisted_apps)
    for name in launcher.available_aliases():
        console.print(name)


@app.command()
def logs(limit: int = typer.Option(20, min=1, max=200)) -> None:
    """List recent run manifests."""
    settings = load_settings()
    runs_dir = settings.runs_dir
    if not runs_dir.exists():
        console.print("No runs yet.")
        return
    manifests = sorted(runs_dir.glob("*/manifest.json"), reverse=True)[:limit]
    table = Table(title="Recent Agent Runs")
    table.add_column("Run")
    table.add_column("Status")
    table.add_column("Task")
    table.add_column("Steps")
    for path in manifests:
        data = json.loads(path.read_text(encoding="utf-8"))
        table.add_row(
            data.get("run_id", path.parent.name),
            str(data.get("status", "unknown")),
            str(data.get("task", ""))[:90],
            str(data.get("steps", "")),
        )
    console.print(table)


@app.command("show-log")
def show_log(run_id: str) -> None:
    """Print the human-readable log for one run."""
    settings = load_settings()
    path = settings.runs_dir / run_id / "agent.log"
    if not path.exists():
        raise typer.BadParameter(f"Run log not found: {path}")
    console.print(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    app()
