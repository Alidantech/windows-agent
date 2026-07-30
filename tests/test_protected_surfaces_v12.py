from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from agent_os.capture import CapturedObservation
from agent_os.models import AgentDecision, Rectangle, TargetInfo, WindowInfo
from agent_os.tools_production_v2 import ToolExecutor
from agent_os.windows import UIASnapshot


def _observation(
    *,
    backend: str = "desktop",
    process: str = "notepad.exe",
    title: str = "Notes",
    url: str | None = None,
) -> CapturedObservation:
    image = Image.new("RGB", (100, 60), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    hwnd = 50 if backend == "desktop" else None
    windows = (
        [
            WindowInfo(
                hwnd=50,
                title=title,
                process_id=500,
                process_name=process,
                rect=Rectangle(left=0, top=0, width=100, height=60),
                active=True,
            )
        ]
        if backend == "desktop"
        else []
    )
    return CapturedObservation(
        target=TargetInfo(
            spec="active-window" if backend == "desktop" else "browser-session",
            kind="window" if backend == "desktop" else "browser",
            label=title,
            rect=Rectangle(left=0, top=0, width=100, height=60),
            hwnd=hwnd,
            backend=backend,
            url=url,
            identity=f"{backend}:{title}",
            capture_source="print-window" if backend == "desktop" else "playwright",
            lease_id="lease-1",
        ),
        monitors=[],
        windows=windows,
        uia=UIASnapshot(elements=[], wrappers={}),
        original_image=image,
        api_image_bytes=buffer.getvalue(),
        screenshot_path=None,
        capture_token="capture",
        state={},
    )


def _executor() -> ToolExecutor:
    executor = ToolExecutor.__new__(ToolExecutor)
    executor.settings = SimpleNamespace(
        enforce_domain_allowlist=False,
        browser_allowed_domains="",
        prompt_injection_policy="block_transmission",
    )
    return executor


def test_terminal_target_is_denied() -> None:
    result = _executor()._protected_surface(
        AgentDecision(action="press_key", key="Enter", reason="Continue"),
        _observation(process="powershell.exe", title="Windows PowerShell"),
    )
    assert result is not None
    assert result.details["protected_surface"] == "denied_desktop_target"


def test_windows_key_shortcut_is_denied() -> None:
    result = _executor()._protected_surface(
        AgentDecision(
            action="hotkey",
            keys=["Windows", "R"],
            reason="Open the Run dialog",
        ),
        _observation(),
    )
    assert result is not None
    assert result.details["protected_surface"] == "windows_key"


def test_password_manager_site_is_denied() -> None:
    result = _executor()._protected_surface(
        AgentDecision(
            action="open_url",
            url="https://vault.bitwarden.com",
            reason="Open the vault",
        ),
        _observation(backend="browser", title="Browser", url="about:blank"),
    )
    assert result is not None
    assert result.details["protected_surface"] == "password_manager_site"
