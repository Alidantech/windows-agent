from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from agent_os.secrets import secret_store

ProviderName = Literal["auto", "gemini", "openai", "mistral"]

DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-3.5-flash-lite",
    "openai": "gpt-5-mini",
    "mistral": "mistral-small-2603",
}

DEFAULT_AUTO_MODELS: tuple[str, ...] = (
    "gemini:gemini-3.5-flash-lite",
    "gemini:gemini-3.6-flash",
    "gemini:gemini-3.1-flash-lite",
    "openai:gpt-5-mini",
    "mistral:mistral-small-2603",
)

PROVIDER_MODEL_ENV: dict[str, str] = {
    "gemini": "GEMINI_MODEL",
    "openai": "OPENAI_MODEL",
    "mistral": "MISTRAL_MODEL",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WINDOWS_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: ProviderName = "auto"
    model: str = "auto"
    auto_models: str = ""
    auto_switch_models: bool = True
    model_cooldown_seconds: int = Field(default=120, ge=5, le=86400)
    max_provider_switches: int = Field(default=5, ge=0, le=20)

    target: str = "monitor:1"
    max_steps: int = Field(default=40, ge=1, le=200)
    repeat_limit: int = Field(default=3, ge=2, le=10)
    step_delay_seconds: float = Field(default=0.8, ge=0.0, le=30.0)
    completion_settle_seconds: float = Field(default=0.8, ge=0.0, le=10.0)
    max_completion_rejections: int = Field(default=2, ge=1, le=5)
    api_retries: int = Field(default=2, ge=1, le=8)
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
    session_history_limit: int = Field(default=12, ge=1, le=100)

    runs_dir: Path = Path("runs")
    state_dir: Path = Path(".windows-agent")
    prompts_dir: Path = Path("prompts")
    skills_dir: Path = Path("skills")
    app_aliases_file: Path = Path("config/apps.yml")


def model_for_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in DEFAULT_MODELS:
        choices = ", ".join(sorted(DEFAULT_MODELS))
        raise RuntimeError(f"Unknown AI provider {provider!r}. Available: {choices}.")
    configured = os.getenv(PROVIDER_MODEL_ENV[normalized], "").strip()
    return configured or DEFAULT_MODELS[normalized]


def parse_model_ref(value: str, default_provider: str | None = None) -> tuple[str, str]:
    text = value.strip()
    if ":" in text:
        provider, model = text.split(":", 1)
        return provider.strip().lower(), model.strip()
    provider = (default_provider or "gemini").strip().lower()
    return provider, text


def configured_model_candidates(settings: Settings) -> list[tuple[str, str]]:
    provider = settings.provider.strip().lower()
    model = settings.model.strip()
    if provider != "auto":
        selected = model if model and model != "auto" else model_for_provider(provider)
        candidates = [(provider, selected)]
        if not settings.auto_switch_models:
            return candidates
        extras = settings.auto_models or ""
        for item in (part.strip() for part in extras.split(",")):
            if item:
                candidate = parse_model_ref(item, provider)
                if candidate not in candidates:
                    candidates.append(candidate)
        return candidates

    raw = settings.auto_models.strip()
    refs = (
        [part.strip() for part in raw.split(",") if part.strip()]
        if raw
        else list(DEFAULT_AUTO_MODELS)
    )
    candidates: list[tuple[str, str]] = []
    for ref in refs:
        candidate = parse_model_ref(ref)
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def load_settings() -> Settings:
    load_dotenv()
    settings = Settings()
    if settings.provider != "auto" and (
        not settings.model.strip() or settings.model == "auto"
    ):
        settings.model = model_for_provider(settings.provider)

    project_root = Path(__file__).resolve().parents[2]
    for field_name in (
        "runs_dir",
        "state_dir",
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
        if field_name in {"browser_profile_dir", "state_dir", "runs_dir"}:
            resolved = cwd_candidate
        else:
            resolved = cwd_candidate if cwd_candidate.exists() else project_candidate
        setattr(settings, field_name, resolved)
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    return settings


def provider_api_key(provider: str) -> str:
    key = secret_store.get(provider)
    if not key:
        raise RuntimeError(
            f"No API key is configured for {provider}. "
            f"Use '/key set {provider}' in Windows Agent."
        )
    return key
