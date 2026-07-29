from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

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


class ScreenCapture:
    def __init__(self, settings: Settings, window_manager: WindowManager | None = None) -> None:
        self.settings = settings
        self.windows = window_manager or WindowManager()

    def list_monitors(self) -> list[MonitorInfo]:
        import mss

        with mss.mss(with_cursor=self.settings.include_cursor) as sct:
            monitors: list[MonitorInfo] = []
            for index, monitor in enumerate(sct.monitors[1:], start=1):
                monitors.append(
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
                )
            return monitors

    @staticmethod
    def _contains(rect: Rectangle, x: float, y: float) -> bool:
        return rect.left <= x < rect.right and rect.top <= y < rect.bottom

    def _monitor_for_window(self, window: WindowInfo, monitors: list[MonitorInfo]) -> MonitorInfo:
        center_x = window.rect.left + window.rect.width / 2
        center_y = window.rect.top + window.rect.height / 2
        for monitor in monitors:
            if self._contains(monitor.rect, center_x, center_y):
                return monitor
        return monitors[0]

    def resolve_target(self, spec: str, monitors: list[MonitorInfo]) -> TargetInfo:
        normalized = spec.strip()
        lowered = normalized.lower()

        if lowered == "desktop":
            left = min(m.rect.left for m in monitors)
            top = min(m.rect.top for m in monitors)
            right = max(m.rect.right for m in monitors)
            bottom = max(m.rect.bottom for m in monitors)
            return TargetInfo(
                spec=spec,
                kind="desktop",
                label="Entire virtual desktop",
                rect=Rectangle(left=left, top=top, width=right - left, height=bottom - top),
            )

        if lowered.startswith("monitor:"):
            index = int(normalized.split(":", 1)[1])
            match = next((monitor for monitor in monitors if monitor.index == index), None)
            if not match:
                raise RuntimeError(f"Monitor {index} does not exist.")
            return TargetInfo(
                spec=spec,
                kind="monitor",
                label=f"Monitor {index}",
                rect=match.rect,
                monitor_index=index,
            )

        if lowered.startswith("window:"):
            pattern = normalized.split(":", 1)[1]
            window = self.windows.find_window(pattern)
            return TargetInfo(
                spec=spec,
                kind="window",
                label=window.title,
                rect=window.rect,
                hwnd=window.hwnd,
            )

        active = self.windows.active_window()
        if lowered == "active-monitor":
            monitor = self._monitor_for_window(active, monitors)
            return TargetInfo(
                spec=spec,
                kind="monitor",
                label=f"Monitor {monitor.index} containing {active.title}",
                rect=monitor.rect,
                monitor_index=monitor.index,
            )

        if lowered in {"active", "active-window"}:
            return TargetInfo(
                spec=spec,
                kind="window",
                label=active.title,
                rect=active.rect,
                hwnd=active.hwnd,
            )

        raise RuntimeError(
            "Unknown target. Use active-window, active-monitor, desktop, monitor:N, or window:TITLE."
        )

    def capture(
        self,
        target_spec: str,
        screenshot_path: Path | None = None,
    ) -> CapturedObservation:
        import mss

        monitors = self.list_monitors()
        target = self.resolve_target(target_spec, monitors)
        region = {
            "left": target.rect.left,
            "top": target.rect.top,
            "width": target.rect.width,
            "height": target.rect.height,
        }

        with mss.mss(with_cursor=self.settings.include_cursor) as sct:
            shot = sct.grab(region)
            image = Image.frombytes("RGB", shot.size, shot.rgb)

        if screenshot_path:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(screenshot_path, format="PNG", optimize=True)

        api_image = image.copy()
        api_image.thumbnail(
            (self.settings.screenshot_max_width, self.settings.screenshot_max_height),
            Image.Resampling.LANCZOS,
        )
        buffer = BytesIO()
        api_image.save(buffer, format="PNG", optimize=True)

        window_summaries = self.windows.list_windows(limit=self.settings.max_window_summaries)
        uia = UIASnapshot(elements=[], wrappers={})
        if self.settings.use_uia and target.hwnd:
            uia = self.windows.snapshot_elements(
                target.hwnd,
                target.rect,
                self.settings.max_ui_elements,
            )

        return CapturedObservation(
            target=target,
            monitors=monitors,
            windows=window_summaries,
            uia=uia,
            original_image=image,
            api_image_bytes=buffer.getvalue(),
            screenshot_path=screenshot_path,
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
        draw.rectangle((8, 8, 8 + max(220, len(label) * 9), 38), fill="white")
        draw.text((14, 14), label, fill="black")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated.save(output_path, format="PNG", optimize=True)
