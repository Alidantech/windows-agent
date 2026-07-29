from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from agent_os.browser import BrowserController
from agent_os.config import Settings
from agent_os.models import MonitorInfo, Rectangle, TargetInfo, WindowInfo
from agent_os.windows import UIASnapshot, WindowManager


@dataclass
class CapturedObservation:
    target: TargetInfo
    monitors: list[MonitorInfo]
    windows: list[WindowInfo]
    uia: UIASnapshot
    original_image: Image.Image
    api_image_bytes: bytes
    screenshot_path: Path | None
    capture_token: str
    state: dict[str, object]


class ScreenCapture:
    def __init__(self, settings: Settings, window_manager: WindowManager | None = None) -> None:
        self.settings = settings
        self.windows = window_manager or WindowManager()

    def list_monitors(self) -> list[MonitorInfo]:
        import mss

        with mss.mss(with_cursor=self.settings.include_cursor) as sct:
            return [
                MonitorInfo(
                    index=index,
                    primary=index == 1,
                    rect=Rectangle(
                        left=int(monitor["left"]),
                        top=int(monitor["top"]),
                        width=int(monitor["width"]),
                        height=int(monitor["height"]),
                    ),
                )
                for index, monitor in enumerate(sct.monitors[1:], start=1)
            ]

    def monitor_for_window(
        self,
        window: WindowInfo,
        monitors: list[MonitorInfo] | None = None,
    ) -> MonitorInfo:
        items = monitors or self.list_monitors()
        pairs = [(item.index, item.rect) for item in items]
        index = self.windows.monitor_for_rect(window.rect, pairs)
        return next((item for item in items if item.index == index), items[0])

    def monitor_by_index(
        self,
        index: int,
        monitors: list[MonitorInfo] | None = None,
    ) -> MonitorInfo:
        items = monitors or self.list_monitors()
        match = next((item for item in items if item.index == index), None)
        if not match:
            raise RuntimeError(f"Monitor {index} does not exist.")
        return match

    def resolve_target(self, spec: str, monitors: list[MonitorInfo]) -> TargetInfo:
        normalized = spec.strip()
        lowered = normalized.lower()
        if lowered == "desktop":
            left = min(item.rect.left for item in monitors)
            top = min(item.rect.top for item in monitors)
            right = max(item.rect.right for item in monitors)
            bottom = max(item.rect.bottom for item in monitors)
            rect = Rectangle(left=left, top=top, width=right - left, height=bottom - top)
            return TargetInfo(
                spec=spec,
                kind="desktop",
                label="Entire virtual desktop",
                rect=rect,
                identity=f"desktop:{left}:{top}:{right}:{bottom}",
            )
        if lowered.startswith("monitor:"):
            index = int(normalized.split(":", 1)[1])
            monitor = self.monitor_by_index(index, monitors)
            return TargetInfo(
                spec=spec,
                kind="monitor",
                label=f"Monitor {index}",
                rect=monitor.rect,
                monitor_index=index,
                identity=(
                    f"monitor:{index}:{monitor.rect.left}:{monitor.rect.top}:"
                    f"{monitor.rect.width}:{monitor.rect.height}"
                ),
            )
        if lowered.startswith("hwnd:"):
            window = self.windows.window_by_hwnd(int(normalized.split(":", 1)[1]))
            monitor = self.monitor_for_window(window, monitors)
            return TargetInfo(
                spec=spec,
                kind="window",
                label=window.title,
                rect=window.rect,
                hwnd=window.hwnd,
                monitor_index=monitor.index,
                identity=f"hwnd:{window.hwnd}",
            )
        if lowered.startswith("window:"):
            window = self.windows.find_window(normalized.split(":", 1)[1])
            monitor = self.monitor_for_window(window, monitors)
            return TargetInfo(
                spec=spec,
                kind="window",
                label=window.title,
                rect=window.rect,
                hwnd=window.hwnd,
                monitor_index=monitor.index,
                identity=f"hwnd:{window.hwnd}",
            )
        if lowered.startswith("process:"):
            window = self.windows.find_process_window(normalized.split(":", 1)[1])
            monitor = self.monitor_for_window(window, monitors)
            return TargetInfo(
                spec=spec,
                kind="window",
                label=window.title,
                rect=window.rect,
                hwnd=window.hwnd,
                monitor_index=monitor.index,
                identity=f"hwnd:{window.hwnd}",
            )
        active = self.windows.active_window()
        if lowered == "active-monitor":
            monitor = self.monitor_for_window(active, monitors)
            return TargetInfo(
                spec=spec,
                kind="monitor",
                label=f"Monitor {monitor.index} containing {active.title}",
                rect=monitor.rect,
                monitor_index=monitor.index,
                identity=f"monitor:{monitor.index}",
            )
        if lowered in {"active", "active-window"}:
            monitor = self.monitor_for_window(active, monitors)
            return TargetInfo(
                spec=spec,
                kind="window",
                label=active.title,
                rect=active.rect,
                hwnd=active.hwnd,
                monitor_index=monitor.index,
                identity=f"hwnd:{active.hwnd}",
            )
        raise RuntimeError(
            "Unknown target. Use active-window, active-monitor, desktop, monitor:N, "
            "window:TITLE, process:NAME, or hwnd:NUMBER."
        )

    def _screen_image(self, rect: Rectangle) -> Image.Image:
        import mss

        region = {"left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height}
        with mss.mss(with_cursor=self.settings.include_cursor) as sct:
            shot = sct.grab(region)
            return Image.frombytes("RGB", shot.size, shot.rgb)

    def _api_bytes(self, image: Image.Image) -> bytes:
        copy = image.copy()
        copy.thumbnail(
            (self.settings.screenshot_max_width, self.settings.screenshot_max_height),
            Image.Resampling.LANCZOS,
        )
        buffer = BytesIO()
        copy.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    @staticmethod
    def _token(target: TargetInfo, png: bytes) -> str:
        return f"{target.identity or target.spec}:{hashlib.sha256(png).hexdigest()[:16]}"

    def _windows_with_monitors(
        self,
        monitors: list[MonitorInfo],
    ) -> list[WindowInfo]:
        windows = self.windows.list_windows(limit=self.settings.max_window_summaries)
        pairs = [(item.index, item.rect) for item in monitors]
        for window in windows:
            window.monitor_index = self.windows.monitor_for_rect(window.rect, pairs)
        return windows

    def capture(
        self,
        target_spec: str,
        screenshot_path: Path | None = None,
        lease_id: str | None = None,
    ) -> CapturedObservation:
        monitors = self.list_monitors()
        target = self.resolve_target(target_spec, monitors)
        target.lease_id = lease_id
        if target.hwnd is not None:
            printed = self.windows.capture_window_image(target.hwnd)
            if printed is not None:
                image = printed
                target.capture_source = "print-window"
            else:
                foreground = self.windows.active_hwnd()
                if self.settings.strict_capture_alignment and foreground != target.hwnd:
                    raise RuntimeError(
                        "The leased HWND could not be captured independently and another window owns "
                        "foreground focus. Strict alignment stopped instead of sending unrelated pixels. "
                        "Use the isolated browser backend, reserve the monitor, or set "
                        "AGENT_OS_STRICT_CAPTURE_ALIGNMENT=false."
                    )
                image = self._screen_image(target.rect)
                target.capture_source = "screen-fallback"
        else:
            image = self._screen_image(target.rect)
            target.capture_source = "screen"
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        png = buffer.getvalue()
        if screenshot_path:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot_path.write_bytes(png)
        uia = UIASnapshot(elements=[], wrappers={})
        if self.settings.use_uia and target.hwnd:
            uia = self.windows.snapshot_elements(target.hwnd, target.rect, self.settings.max_ui_elements)
        return CapturedObservation(
            target=target,
            monitors=monitors,
            windows=self._windows_with_monitors(monitors),
            uia=uia,
            original_image=image,
            api_image_bytes=self._api_bytes(image),
            screenshot_path=screenshot_path,
            capture_token=self._token(target, png),
            state={"backend": "desktop", "target_identity": target.identity},
        )

    def capture_browser(
        self,
        browser: BrowserController,
        monitor_index: int | None,
        screenshot_path: Path | None = None,
        lease_id: str | None = None,
    ) -> CapturedObservation:
        monitors = self.list_monitors()
        snapshot = browser.capture(screenshot_path)
        target = TargetInfo(
            spec="browser-session",
            kind="browser",
            label=f"{snapshot.title} — isolated {snapshot.browser_name}",
            rect=snapshot.viewport,
            monitor_index=monitor_index,
            backend="browser",
            url=snapshot.url,
            identity=f"browser:{snapshot.browser_name}:{snapshot.url}",
            capture_source="playwright",
            lease_id=lease_id,
        )
        return CapturedObservation(
            target=target,
            monitors=monitors,
            windows=self._windows_with_monitors(monitors),
            uia=snapshot.uia,
            original_image=snapshot.image,
            api_image_bytes=self._api_bytes(snapshot.image),
            screenshot_path=screenshot_path,
            capture_token=self._token(target, snapshot.image_bytes),
            state={"backend": "browser", **browser.diagnostics(clear=False)},
        )

    @staticmethod
    def annotate_action(
        image: Image.Image,
        action: str,
        x: int | None,
        y: int | None,
        output_path: Path,
    ) -> None:
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        label = action
        if x is not None and y is not None:
            px = round(x * max(1, annotated.width - 1) / 1000)
            py = round(y * max(1, annotated.height - 1) / 1000)
            radius = 18
            draw.ellipse((px - radius, py - radius, px + radius, py + radius), outline="red", width=4)
            draw.line((px - radius * 2, py, px + radius * 2, py), fill="red", width=2)
            draw.line((px, py - radius * 2, px, py + radius * 2), fill="red", width=2)
            label = f"{action} @ ({x}, {y})"
        draw.rectangle((8, 8, 8 + max(240, len(label) * 9), 40), fill="white")
        draw.text((14, 15), label, fill="black")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated.save(output_path, format="PNG", optimize=True)
