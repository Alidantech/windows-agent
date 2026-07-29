from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from urllib.parse import urlparse

from agent_os.models import AgentDecision, ExecutionResult, MonitorInfo, Rectangle, WindowInfo
from agent_os.targeting import title_tokens
from agent_os.windows import WindowManager


@dataclass
class TargetLease:
    requested_spec: str
    controller_hwnd: int
    controller_title: str
    lease_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    monitor_index: int | None = None
    monitor_rect: Rectangle | None = None
    backend: str = "desktop"
    bound_hwnd: int | None = None
    bound_title: str | None = None
    bound_process: str | None = None
    state: str = "discovering"
    reason: str | None = None
    generation: int = 0

    @property
    def is_bound(self) -> bool:
        return self.backend == "browser" or self.bound_hwnd is not None

    @property
    def capture_spec(self) -> str:
        if self.backend == "browser":
            return "browser-session"
        if self.bound_hwnd is not None:
            return f"hwnd:{self.bound_hwnd}"
        if self.monitor_index is not None:
            return f"monitor:{self.monitor_index}"
        return "desktop"

    def bind_window(self, window: WindowInfo, reason: str) -> bool:
        changed = self.backend != "desktop" or self.bound_hwnd != window.hwnd
        self.backend = "desktop"
        self.bound_hwnd = window.hwnd
        self.bound_title = window.title
        self.bound_process = window.process_name
        self.state = "bound"
        self.reason = reason
        if changed:
            self.generation += 1
        return changed

    def bind_browser(self, title: str | None = None) -> bool:
        changed = self.backend != "browser"
        self.backend = "browser"
        self.bound_hwnd = None
        self.bound_title = title or "Isolated browser"
        self.bound_process = "playwright"
        self.state = "bound"
        self.reason = "isolated Playwright browser session"
        if changed:
            self.generation += 1
        return changed

    def as_dict(self) -> dict[str, object]:
        return {
            "lease_id": self.lease_id,
            "requested_spec": self.requested_spec,
            "state": self.state,
            "backend": self.backend,
            "monitor_index": self.monitor_index,
            "monitor_rect": self.monitor_rect.model_dump() if self.monitor_rect else None,
            "bound_hwnd": self.bound_hwnd,
            "bound_title": self.bound_title,
            "bound_process": self.bound_process,
            "reason": self.reason,
            "generation": self.generation,
            "capture_spec": self.capture_spec,
        }

    def label(self) -> str:
        monitor = f"monitor {self.monitor_index}" if self.monitor_index else "unassigned monitor"
        if self.backend == "browser":
            return f"lease {self.lease_id}: isolated browser on {monitor}"
        if self.bound_hwnd:
            return f"lease {self.lease_id}: {self.bound_title} [{self.bound_hwnd}] on {monitor}"
        return f"lease {self.lease_id}: discovering on {monitor}"


class LeaseManager:
    def __init__(
        self,
        windows: WindowManager,
        monitors: list[MonitorInfo],
        controller: WindowInfo,
        target_spec: str,
        move_window: bool,
    ) -> None:
        self.windows = windows
        self.monitors = monitors
        self.controller = controller
        self.move_window = move_window
        self.lease = TargetLease(
            requested_spec=target_spec,
            controller_hwnd=controller.hwnd,
            controller_title=controller.title,
        )
        self._initialize(target_spec)

    def _monitor(self, index: int) -> MonitorInfo:
        match = next((item for item in self.monitors if item.index == index), None)
        if not match:
            available = ", ".join(str(item.index) for item in self.monitors)
            raise RuntimeError(f"Monitor {index} does not exist. Available: {available}")
        return match

    def _monitor_for_window(self, window: WindowInfo) -> MonitorInfo | None:
        pairs = [(item.index, item.rect) for item in self.monitors]
        index = self.windows.monitor_for_rect(window.rect, pairs)
        return next((item for item in self.monitors if item.index == index), None)

    def _assign_monitor(self, monitor: MonitorInfo) -> None:
        self.lease.monitor_index = monitor.index
        self.lease.monitor_rect = monitor.rect

    def _initialize(self, spec: str) -> None:
        value = spec.strip()
        lowered = value.lower()
        if lowered.startswith("monitor:"):
            self._assign_monitor(self._monitor(int(value.split(":", 1)[1])))
            return
        if lowered.startswith("hwnd:"):
            window = self.windows.window_by_hwnd(int(value.split(":", 1)[1]))
            monitor = self._monitor_for_window(window)
            if monitor:
                self._assign_monitor(monitor)
            self.lease.bind_window(window, "explicit HWND target")
            return
        if lowered.startswith("window:"):
            window = self.windows.find_window(value.split(":", 1)[1])
            monitor = self._monitor_for_window(window)
            if monitor:
                self._assign_monitor(monitor)
            self.lease.bind_window(window, "matched requested window")
            return
        if lowered.startswith("process:"):
            window = self.windows.find_process_window(value.split(":", 1)[1])
            monitor = self._monitor_for_window(window)
            if monitor:
                self._assign_monitor(monitor)
            self.lease.bind_window(window, "matched requested process")
            return
        if lowered == "active-monitor":
            active = self.windows.active_window()
            monitor = self._monitor_for_window(active)
            if monitor:
                self._assign_monitor(monitor)
            if active.hwnd != self.controller.hwnd:
                self.lease.bind_window(active, "active window on active monitor")
            return
        if lowered in {"active", "active-window"}:
            active = self.windows.active_window()
            if active.hwnd != self.controller.hwnd:
                monitor = self._monitor_for_window(active)
                if monitor:
                    self._assign_monitor(monitor)
                self.lease.bind_window(active, "active window at task start")
            return
        if lowered == "desktop":
            return
        raise RuntimeError(
            "Unknown target. Use active-window, active-monitor, desktop, monitor:N, "
            "window:TITLE, process:NAME, or hwnd:NUMBER."
        )

    def bind_window(self, window: WindowInfo, reason: str) -> bool:
        if self.lease.monitor_rect is None:
            monitor = self._monitor_for_window(window)
            if monitor:
                self._assign_monitor(monitor)
        if self.lease.monitor_rect is not None and self.move_window:
            current = self._monitor_for_window(window)
            if current is None or current.index != self.lease.monitor_index:
                window = self.windows.move_to_monitor(window.hwnd, self.lease.monitor_rect)
        return self.lease.bind_window(window, reason)

    @staticmethod
    def _domain_terms(url: str | None) -> set[str]:
        if not url:
            return set()
        normalized = url if "://" in url else f"https://{url}"
        host = urlparse(normalized).hostname or ""
        return title_tokens(host.replace(".", " "))

    def _candidate_score(
        self,
        window: WindowInfo,
        before_hwnds: set[int],
        decision: AgentDecision,
    ) -> float:
        if window.hwnd == self.controller.hwnd:
            return -1000.0
        score = 0.0
        if window.hwnd not in before_hwnds:
            score += 45.0
        if window.active:
            score += 25.0
        process = (window.process_name or "").lower()
        if decision.action == "open_url" and process in self.windows.BROWSER_PROCESSES:
            score += 28.0
        if self.lease.monitor_rect:
            overlap = window.rect.intersection_area(self.lease.monitor_rect)
            score += 25.0 * overlap / max(1, window.rect.width * window.rect.height)
        terms = self._domain_terms(decision.url)
        if terms:
            title_set = title_tokens(window.title)
            score += 35.0 * len(terms & title_set) / len(terms)
        if decision.app:
            app_terms = title_tokens(decision.app)
            window_terms = title_tokens(f"{window.title} {window.process_name or ''}")
            if app_terms:
                score += 25.0 * len(app_terms & window_terms) / len(app_terms)
        return score

    def discover_after_action(
        self,
        decision: AgentDecision,
        result: ExecutionResult,
        before_windows: list[WindowInfo],
        timeout: float = 5.0,
    ) -> tuple[bool, str | None]:
        if not result.ok or self.lease.backend == "browser":
            return False, None
        hwnd = result.details.get("hwnd")
        if isinstance(hwnd, int):
            changed = self.bind_window(self.windows.window_by_hwnd(hwnd), f"{decision.action} returned HWND")
            return changed, self.lease.label()
        if decision.action not in {"launch_app", "open_url", "activate_window"}:
            return False, None
        before_hwnds = {item.hwnd for item in before_windows}
        deadline = time.monotonic() + timeout
        best: tuple[float, WindowInfo] | None = None
        while time.monotonic() < deadline:
            for window in self.windows.list_windows(limit=300):
                score = self._candidate_score(window, before_hwnds, decision)
                if best is None or score > best[0]:
                    best = (score, window)
            if best and best[0] >= 55.0:
                changed = self.bind_window(best[1], f"discovered destination after {decision.action}")
                return changed, self.lease.label()
            time.sleep(0.3)
        if best and best[0] >= 35.0:
            changed = self.bind_window(best[1], f"best available destination after {decision.action}")
            return changed, self.lease.label()
        return False, None

    def refresh(self) -> WindowInfo | None:
        if self.lease.backend == "browser" or self.lease.bound_hwnd is None:
            return None
        window = self.windows.window_by_hwnd(self.lease.bound_hwnd)
        self.lease.bound_title = window.title
        self.lease.bound_process = window.process_name
        return window
