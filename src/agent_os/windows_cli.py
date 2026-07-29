from __future__ import annotations

import importlib
import os
import platform
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from agent_os.apps import AppLauncher
from agent_os.capture import ScreenCapture
from agent_os.cli import app
from agent_os.config import (
    CURRENT_ENV_PREFIX,
    PROVIDER_MODEL_ENV,
    load_settings,
    model_for_provider,
    provider_api_key,
)
from agent_os.providers import available_providers
from agent_os.windows import WindowManager

console = Console()
app.info.name = "windows-agent"
app.info.help = "Provider-ready Windows automation with isolated browser control."


@app.callback()
def windows_agent_options(
    provider: str | None = typer.Option(None, "--provider", help="AI provider: gemini, openai, or mistral. Must appear before the command."),
    model: str | None = typer.Option(None, "--model", help="Model override. Must appear before the command."),
) -> None:
    """Configure the provider before running any Windows Agent command."""
    if provider is not None:
        normalized = provider.strip().lower()
        if normalized not in available_providers():
            choices = ", ".join(available_providers())
            raise typer.BadParameter(f"Unknown provider {provider!r}. Use one of: {choices}.")
        os.environ[f"{CURRENT_ENV_PREFIX}PROVIDER"] = normalized
        if model is None:
            os.environ[f"{CURRENT_ENV_PREFIX}MODEL"] = model_for_provider(normalized)
    if model is not None:
        normalized_model = model.strip()
        if not normalized_model:
            raise typer.BadParameter("Model cannot be empty.")
        os.environ[f"{CURRENT_ENV_PREFIX}MODEL"] = normalized_model


def provider_doctor() -> None:
    """Validate the selected provider, Windows access, and browser runtime."""
    if platform.system() != "Windows":
        raise typer.BadParameter("Windows Agent controls Windows and must run on Windows.")
    settings = load_settings()
    modules = {"gemini": "google.genai", "openai": "openai", "mistral": "mistralai"}
    table = Table(title="Windows Agent v0.5 Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")
    table.add_row("Python", "OK", sys.version.split()[0])
    table.add_row("Platform", "OK", platform.platform())
    try:
        importlib.import_module(modules[settings.provider])
        table.add_row(f"{settings.provider.title()} SDK", "OK", modules[settings.provider])
    except Exception as exc:
        table.add_row(f"{settings.provider.title()} SDK", "FAILED", str(exc))
    try:
        key = provider_api_key(settings.provider)
        table.add_row(f"{settings.provider.title()} key", "OK", f"configured ({len(key)} characters; hidden)")
    except Exception as exc:
        table.add_row(f"{settings.provider.title()} key", "FAILED", str(exc))
    try:
        table.add_row("Monitors", "OK", f"detected {len(ScreenCapture(settings).list_monitors())}")
    except Exception as exc:
        table.add_row("Monitors", "FAILED", str(exc))
    try:
        table.add_row("Visible windows", "OK", f"detected at least {len(WindowManager().list_windows(limit=10))}")
    except Exception as exc:
        table.add_row("Visible windows", "FAILED", str(exc))
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
            table.add_row("Playwright Chromium", "OK" if executable.exists() else "MISSING", str(executable) if executable.exists() else "Run: windows-agent browser-install")
    except Exception as exc:
        table.add_row("Playwright Chromium", "FAILED", str(exc))
    aliases = AppLauncher(settings.app_aliases_file, settings.allow_unlisted_apps)
    table.add_row("App aliases", "OK", ", ".join(aliases.available_aliases()))
    table.add_row("Provider", "OK", settings.provider)
    table.add_row("Model", "OK", settings.model)
    table.add_row("Control mode", "OK", settings.control_mode)
    table.add_row("Physical fallback", "OK", settings.physical_input_policy)
    console.print(table)


for command in app.registered_commands:
    callback = getattr(command, "callback", None)
    if getattr(command, "name", None) == "doctor" or getattr(callback, "__name__", "") == "doctor":
        command.callback = provider_doctor
        command.name = "doctor"
        break


@app.command("providers")
def list_providers() -> None:
    """List built-in providers, selected model, and optional SDK status."""
    settings = load_settings()
    modules = {"gemini": "google.genai", "openai": "openai", "mistral": "mistralai"}
    extras = {"gemini": ".", "openai": ".[openai]", "mistral": ".[mistral]"}
    table = Table(title="Windows Agent AI Providers")
    table.add_column("Provider")
    table.add_column("Selected")
    table.add_column("SDK")
    table.add_column("Default/configured model")
    table.add_column("Install")
    for name in available_providers():
        try:
            importlib.import_module(modules[name])
            sdk = "installed"
        except Exception:
            sdk = "missing"
        configured = settings.model if name == settings.provider else os.getenv(PROVIDER_MODEL_ENV[name], "").strip() or model_for_provider(name)
        table.add_row(name, "yes" if name == settings.provider else "", sdk, configured, Text(f'python -m pip install -e "{extras[name]}"'))
    console.print(table)
