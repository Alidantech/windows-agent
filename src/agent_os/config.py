from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["gemini", "openai", "mistral"]

CURRENT_ENV_PREFIX = "WINDOWS_AGENT_"
LEGACY_ENV_PREFIX = "AGENT_OS_"

DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-3.5-flash-lite",
    "openai": "gpt-5-mini",
    "mistral": "mistral-small-latest",
}

PROVIDER_KEY_ENV: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}

PROVIDER_MODEL_ENV: dict[str, str] = {
    "gemini": "GEMINI_MODEL",
    "openai": "OPENAI_MODEL",
    "mistral": "MISTRAL_MODEL",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix=CURRENT_ENV_PREFIX,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: ProviderName = "gemini"
    model: str = ""
    target: str = "active-window"
    max_steps: int = Field(default=40, ge=1, le=200)
    repeat_limit: int = Field(default=3, ge=2, le=10)
    step_delay_seconds: float = Field(default=0.8, ge=0.0, le=30.0)
    api_retries: int = Field(default=3, ge=1, le=8)
    api_retry_base_seconds: float = Field(default=1.5, ge=0.1, le=20.0)
    api_timeout_ms: int = Field(default=30000, ge=3000, le=180000)

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
    browser_profile_dir: Path = Path(".windows-agent/browser-profile")
    browser_timeout_ms: int = Field(default=20000, ge=1000, le=120000)
    browser_smoke_max_links: int = Field(default=60, ge=1, le=250)
    browser_smoke_visual_delay_ms: int = Field(default=350, ge=0, le=5000)

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


def _promote_legacy_environment() -> None:
    """Copy legacy AGENT_OS_* values into WINDOWS_AGENT_* when not overridden.

    This lets existing v0.4 .env files continue working while all new examples
    and documentation use the Windows Agent product name.
    """

    for name, value in tuple(os.environ.items()):
        if not name.startswith(LEGACY_ENV_PREFIX):
            continue
        current_name = CURRENT_ENV_PREFIX + name[len(LEGACY_ENV_PREFIX) :]
        os.environ.setdefault(current_name, value)


def model_for_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in DEFAULT_MODELS:
        choices = ", ".join(sorted(DEFAULT_MODELS))
        raise RuntimeError(f"Unknown AI provider {provider!r}. Available providers: {choices}.")
    provider_model = os.getenv(PROVIDER_MODEL_ENV[normalized], "").strip()
    return provider_model or DEFAULT_MODELS[normalized]


def _resolve_model(settings: Settings) -> str:
    if settings.model.strip():
        return settings.model.strip()
    return model_for_provider(settings.provider)


def load_settings() -> Settings:
    load_dotenv()
    _promote_legacy_environment()
    settings = Settings()
    settings.model = _resolve_model(settings)

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


def provider_api_key(provider: str) -> str:
    load_dotenv()
    normalized = provider.strip().lower()
    env_name = PROVIDER_KEY_ENV.get(normalized)
    if env_name is None:
        choices = ", ".join(sorted(PROVIDER_KEY_ENV))
        raise RuntimeError(f"Unknown AI provider {provider!r}. Available providers: {choices}.")
    key = os.getenv(env_name, "").strip()
    if not key:
        raise RuntimeError(
            f"{env_name} is missing for provider {normalized!r}. "
            "Copy .env.example to .env and add the selected provider key."
        )
    return key


def gemini_api_key() -> str:
    """Backward-compatible key accessor for integrations importing this function."""

    return provider_api_key("gemini")
