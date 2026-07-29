from __future__ import annotations

import importlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from agent_os.agent import DesktopAgent
from agent_os.apps import AppLauncher
from agent_os.capture import ScreenCapture
from agent_os.config import Settings, gemini_api_key, load_settings
from agent_os.lease import LeaseManager
from agent_os.windows import WindowManager

app = typer.Typer(
    name="agent-os",
    help="Monitor-leased Gemini Windows automation with isolated browser control.",
    no_args_is_help=True,
)
console = Console()

ControlMode = Literal["auto", "browser", "desktop"]
BrowserBackend = Literal["isolated", "system"]
ConflictPolicy = Literal["cooperative", "exclusive"]
PhysicalInputPolicy = Literal["deny", "ask", "allow"]


def _require_windows() -> None:
    if platform.system() != "Windows":
        raise typer.BadParameter("Agent OS controls Windows and must run on Windows.")


def _project_path(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _apply_runtime_settings(
    settings: Settings,
    *,
    control_mode: str | None = None,
    browser_backend: str | None = None,
    conflict_policy: str | None = None,
    physical_input: str | None = None,
    overlay: bool | None = None,
    move_window: bool | None = None,
) -> Settings:
    allowed = {
        "control_mode": {"auto", "browser", "desktop"},
        "browser_backend": {"isolated", "system"},
        "conflict_policy": {"cooperative", "exclusive"},
        "physical_input_policy": {"deny", "ask", "allow"},
    }
    values = {
        "control_mode": control_mode,
        "browser_backend": browser_backend,
        "conflict_policy": conflict_policy,
        "physical_input_policy": physical_input,
    }
    for field, value in values.items():
        if value is None:
            continue
        normalized = value.strip().lower()
        if normalized not in allowed[field]:
            choices = ", ".join(sorted(allowed[field]))
            raise typer.BadParameter(f"Invalid {field}: {value!r}. Use one of: {choices}.")
        setattr(settings, field, normalized)
    if overlay is not None:
        settings.overlay_enabled = overlay
    if move_window is not None:
        settings.move_bound_window_to_monitor = move_window
    return settings


def _make_agent(
    settings: Settings,
    *,
    dry_run: bool,
    yes: bool,
) -> DesktopAgent:
    return DesktopAgent(settings, dry_run=dry_run, auto_confirm=yes)


def _print_outcome(outcome) -> None:
    status = "green" if outcome.success else "red"
    console.print(f"\n[{status}]{outcome.summary}[/{status}]")
    console.print(f"Logs and screenshots: [cyan]{outcome.run_dir}[/cyan]")


@app.command()
def doctor() -> None:
    """Validate packages, Gemini configuration, Playwright, monitors, and Windows access."""
    _require_windows()
    settings = load_settings()
    table = Table(title="Agent OS v0.3 Doctor")
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
        "playwright.sync_api",
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

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
            if executable.exists():
                table.add_row("Playwright Chromium", "OK", str(executable))
            else:
                table.add_row(
                    "Playwright Chromium",
                    "MISSING",
                    "Run: python -m playwright install chromium",
                )
    except Exception as exc:
        table.add_row("Playwright Chromium", "FAILED", str(exc))

    aliases = AppLauncher(settings.app_aliases_file, settings.allow_unlisted_apps)
    table.add_row("App aliases", "OK", ", ".join(aliases.available_aliases()))
    table.add_row("Model", "OK", settings.model)
    table.add_row("Control mode", "OK", settings.control_mode)
    table.add_row("Browser backend", "OK", settings.browser_backend)
    table.add_row("Conflict policy", "OK", settings.conflict_policy)
    table.add_row("Physical fallback", "OK", settings.physical_input_policy)
    console.print(table)


@app.command("browser-install")
def browser_install() -> None:
    """Install the isolated Playwright Chromium runtime."""
    command = [sys.executable, "-m", "playwright", "install", "chromium"]
    console.print("Running: [cyan]" + " ".join(command) + "[/cyan]")
    result = subprocess.run(command, check=False)
    raise typer.Exit(code=result.returncode)


@app.command("screens")
def screens_command() -> None:
    """List monitors, exact HWND targets, processes, and fuzzy window targets."""
    _require_windows()
    settings = load_settings()
    capture = ScreenCapture(settings)
    windows = WindowManager()
    monitors = capture.list_monitors()

    monitor_table = Table(title="Monitors")
    monitor_table.add_column("Target")
    monitor_table.add_column("Primary")
    monitor_table.add_column("Left")
    monitor_table.add_column("Top")
    monitor_table.add_column("Size")
    for monitor in monitors:
        monitor_table.add_row(
            f"monitor:{monitor.index}",
            "yes" if monitor.primary else "",
            str(monitor.rect.left),
            str(monitor.rect.top),
            f"{monitor.rect.width}x{monitor.rect.height}",
        )
    console.print(monitor_table)

    pairs = [(item.index, item.rect) for item in monitors]
    window_table = Table(title="Visible Windows")
    window_table.add_column("Active")
    window_table.add_column("Monitor")
    window_table.add_column("HWND")
    window_table.add_column("Process")
    window_table.add_column("Title")
    window_table.add_column("Exact target")
    for window in windows.list_windows(limit=100):
        monitor = windows.monitor_for_rect(window.rect, pairs)
        window_table.add_row(
            "*" if window.active else "",
            str(monitor or ""),
            str(window.hwnd),
            window.process_name or "",
            window.title,
            f"hwnd:{window.hwnd}",
        )
    console.print(window_table)
    console.print(
        "[dim]Use hwnd:NUMBER for an exact lease, process:chrome for a process match, "
        "or window:TITLE for fuzzy title matching. Browser suffixes such as Chrome/Brave/Edge "
        "are treated as interchangeable during fuzzy matching.[/dim]"
    )


@app.command("lease-preview")
def lease_preview(
    target: str = typer.Option(..., help="monitor:N, hwnd:N, process:NAME, or window:TITLE"),
) -> None:
    """Resolve a target without taking actions and show the resulting control lease."""
    _require_windows()
    settings = load_settings()
    windows = WindowManager()
    capture = ScreenCapture(settings, windows)
    controller = windows.active_window()
    manager = LeaseManager(
        windows,
        capture.list_monitors(),
        controller,
        target,
        settings.move_bound_window_to_monitor,
    )
    console.print_json(data=manager.lease.as_dict())


@app.command()
def capture(
    target: str | None = typer.Option(
        None,
        help="active-window, monitor:N, desktop, window:TITLE, process:NAME, or hwnd:N",
    ),
    output: Path = typer.Option(Path("capture.png"), help="PNG output path"),
) -> None:
    """Capture exactly what a desktop control lease would see."""
    _require_windows()
    settings = load_settings()
    chosen_target = target or settings.target
    output = _project_path(output)
    observation = ScreenCapture(settings).capture(chosen_target, screenshot_path=output)
    console.print(f"Saved [bold]{observation.target.label}[/bold] to [cyan]{output}[/cyan]")
    console.print(
        f"Source={observation.target.capture_source}; identity={observation.target.identity}; "
        f"token={observation.capture_token}; size={observation.original_image.width}x"
        f"{observation.original_image.height}; UI elements={len(observation.uia.elements)}"
    )


@app.command("inspect")
def inspect_screen(
    target: str | None = typer.Option(None, help="Desktop screen/window target"),
    output: Path = typer.Option(Path("screen-inspection.json"), help="JSON output path"),
) -> None:
    """Export pixels, capture identity, monitor layout, windows, and UI elements."""
    _require_windows()
    settings = load_settings()
    chosen_target = target or settings.target
    output = _project_path(output)
    screenshot_path = output.with_suffix(".png")
    observation = ScreenCapture(settings).capture(chosen_target, screenshot_path=screenshot_path)
    data = {
        "target": observation.target.model_dump(),
        "capture_token": observation.capture_token,
        "capture_state": observation.state,
        "monitors": [item.model_dump() for item in observation.monitors],
        "visible_windows": [item.model_dump() for item in observation.windows],
        "ui_elements": [item.model_dump() for item in observation.uia.elements],
        "screenshot": str(screenshot_path),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"Inspection JSON: [cyan]{output}[/cyan]")
    console.print(f"Inspection screenshot: [cyan]{screenshot_path}[/cyan]")
    console.print(
        f"Capture source: {observation.target.capture_source}; "
        f"identity: {observation.target.identity}; token: {observation.capture_token}"
    )


def _runtime_options(
    settings: Settings,
    control_mode: str | None,
    browser_backend: str | None,
    conflict_policy: str | None,
    physical_input: str | None,
    no_overlay: bool,
    keep_window_position: bool,
) -> Settings:
    return _apply_runtime_settings(
        settings,
        control_mode=control_mode,
        browser_backend=browser_backend,
        conflict_policy=conflict_policy,
        physical_input=physical_input,
        overlay=False if no_overlay else None,
        move_window=False if keep_window_position else None,
    )


@app.command()
def run(
    task: str = typer.Argument(..., help="Natural-language computer task"),
    target: str | None = typer.Option(None, help="Control target/monitor lease"),
    max_steps: int | None = typer.Option(None, min=1, max=200),
    dry_run: bool = typer.Option(False, help="Plan and log without executing"),
    yes: bool = typer.Option(False, "--yes", help="Auto-confirm locally classified risky actions"),
    non_interactive: bool = typer.Option(False, help="Stop instead of asking for guidance"),
    control_mode: str | None = typer.Option(None, help="auto, browser, or desktop"),
    browser_backend: str | None = typer.Option(None, help="isolated or system"),
    conflict_policy: str | None = typer.Option(None, help="cooperative or exclusive"),
    physical_input: str | None = typer.Option(None, help="deny, ask, or allow"),
    no_overlay: bool = typer.Option(False, "--no-overlay", help="Disable monitor border and virtual cursor"),
    keep_window_position: bool = typer.Option(False, "--keep-window-position", help="Do not move a bound app to its monitor"),
) -> None:
    """Run one task with a stable target lease."""
    _require_windows()
    settings = _runtime_options(
        load_settings(),
        control_mode,
        browser_backend,
        conflict_policy,
        physical_input,
        no_overlay,
        keep_window_position,
    )
    chosen_target = target or settings.target
    agent = _make_agent(settings, dry_run=dry_run, yes=yes)
    try:
        outcome = agent.run(
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
    finally:
        agent.close()

    _print_outcome(outcome)
    raise typer.Exit(code=0 if outcome.success else 2)


@app.command()
def chat(
    target: str | None = typer.Option(None, help="Persistent target/monitor lease"),
    dry_run: bool = typer.Option(False),
    yes: bool = typer.Option(False, "--yes"),
    control_mode: str | None = typer.Option(None, help="auto, browser, or desktop"),
    browser_backend: str | None = typer.Option(None, help="isolated or system"),
    conflict_policy: str | None = typer.Option(None, help="cooperative or exclusive"),
    physical_input: str | None = typer.Option(None, help="deny, ask, or allow"),
    no_overlay: bool = typer.Option(False, "--no-overlay"),
    keep_window_position: bool = typer.Option(False, "--keep-window-position"),
) -> None:
    """Keep one isolated browser/controller alive while assigning multiple tasks."""
    _require_windows()
    settings = _runtime_options(
        load_settings(),
        control_mode,
        browser_backend,
        conflict_policy,
        physical_input,
        no_overlay,
        keep_window_position,
    )
    chosen_target = target or settings.target
    agent = _make_agent(settings, dry_run=dry_run, yes=yes)
    console.print("[bold cyan]Agent OS v0.3 interactive console[/bold cyan]")
    console.print(f"Persistent requested target: [bold]{chosen_target}[/bold]")
    console.print(
        f"Mode={settings.control_mode}; browser={settings.browser_backend}; "
        f"conflicts={settings.conflict_policy}; physical={settings.physical_input_policy}"
    )
    console.print("Enter one task at a time. Type EXIT to close.\n")

    try:
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
                outcome = agent.run(task, target_spec=chosen_target, interactive=True)
                console.print(f"Result: {outcome.summary}")
                console.print(f"Run: {outcome.run_dir}\n")
            except KeyboardInterrupt:
                console.print("\n[yellow]Current task stopped. Console remains open.[/yellow]")
            except Exception as exc:
                console.print(f"[red]Task failed:[/red] {exc}\n")
    finally:
        agent.close()


@app.command()
def apps() -> None:
    """Show allowed application aliases."""
    settings = load_settings()
    launcher = AppLauncher(settings.app_aliases_file, settings.allow_unlisted_apps)
    for name in launcher.available_aliases():
        console.print(name)


@app.command()
def logs(limit: int = typer.Option(20, min=1, max=200)) -> None:
    """List recent run manifests."""
    settings = load_settings()
    if not settings.runs_dir.exists():
        console.print("No runs yet.")
        return
    manifests = sorted(settings.runs_dir.glob("*/manifest.json"), reverse=True)[:limit]
    table = Table(title="Recent Agent Runs")
    table.add_column("Run")
    table.add_column("Status")
    table.add_column("Task")
    table.add_column("Steps")
    table.add_column("Backend")
    for path in manifests:
        data = json.loads(path.read_text(encoding="utf-8"))
        lease = data.get("control_lease") or {}
        table.add_row(
            data.get("run_id", path.parent.name),
            str(data.get("status", "unknown")),
            str(data.get("task", ""))[:80],
            str(data.get("steps", "")),
            str(lease.get("backend", "")),
        )
    console.print(table)


@app.command("show-log")
def show_log(run_id: str) -> None:
    """Print one human-readable run log."""
    settings = load_settings()
    path = settings.runs_dir / run_id / "agent.log"
    if not path.exists():
        raise typer.BadParameter(f"Run log not found: {path}")
    console.print(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    app()
