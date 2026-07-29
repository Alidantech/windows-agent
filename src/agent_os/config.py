from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_OS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str = "gemini-3.5-flash-lite"
    target: str = "active-window"
    max_steps: int = Field(default=40, ge=1, le=200)
    repeat_limit: int = Field(default=3, ge=2, le=10)
    step_delay_seconds: float = Field(default=0.8, ge=0.0, le=30.0)
    api_retries: int = Field(default=3, ge=1, le=8)
    api_retry_base_seconds: float = Field(default=1.5, ge=0.1, le=20.0)

    save_screenshots: bool = True
    screenshot_max_width: int = Field(default=1600, ge=640, le=3840)
    screenshot_max_height: int = Field(default=1200, ge=480, le=2160)
    include_cursor: bool = False
    strict_capture_alignment: bool = True

    use_uia: bool = True
    max_ui_elements: int = Field(default=140, ge=0, le=500)
    max_window_summaries: int = Field(default=50, ge=0, le=200)

    confirm_risky: bool = True
    verify_done: bool = True
    allow_unlisted_apps: bool = False
    max_typed_chars: int = Field(default=3000, ge=1, le=20000)

    control_mode: Literal["auto", "browser", "desktop"] = "auto"
    browser_backend: Literal["isolated", "system"] = "isolated"
    browser_channel: str = "chrome"
    browser_profile_dir: Path = Path(".agent-os/browser-profile")
    browser_timeout_ms: int = Field(default=20000, ge=1000, le=120000)
    browser_smoke_max_links: int = Field(default=60, ge=1, le=250)

    conflict_policy: Literal["cooperative", "exclusive"] = "cooperative"
    physical_input_policy: Literal["deny", "ask", "allow"] = "deny"
    cursor_activity_guard: bool = True
    restore_user_cursor: bool = True
    move_bound_window_to_monitor: bool = True

    overlay_enabled: bool = True

    runs_dir: Path = Path("runs")
    prompts_dir: Path = Path("prompts")
    skills_dir: Path = Path("skills")
    app_aliases_file: Path = Path("config/apps.yml")


def load_settings() -> Settings:
    load_dotenv()
    settings = Settings()
    gemini_model = os.getenv("GEMINI_MODEL", "").strip()
    if gemini_model:
        settings.model = gemini_model

    project_root = Path(__file__).resolve().parents[2]
    for field_name in (
        "runs_dir",
        "prompts_dir",
        "skills_dir",
        "app_aliases_file",
        "browser_profile_dir",
    ):
        value = Path(getattr(settings, field_name))
        if value.is_absolute():
            continue
        cwd_candidate = Path.cwd() / value
        project_candidate = project_root / value
        if field_name == "browser_profile_dir":
            resolved = cwd_candidate
        else:
            resolved = cwd_candidate if cwd_candidate.exists() else project_candidate
        setattr(settings, field_name, resolved)
    return settings


def gemini_api_key() -> str:
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is missing. Copy .env.example to .env and add a key.")
    return key
