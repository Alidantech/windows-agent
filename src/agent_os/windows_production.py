from __future__ import annotations

from typing import Any

from agent_os.targeting import window_match_score
from agent_os.windows import WindowManager as BaseWindowManager


class WindowManager(BaseWindowManager):
    """Require unique returned windows and expose modal/desktop-lock diagnostics."""

    @staticmethod
    def _normalized(value: str) -> str:
        return " ".join(value.casefold().split())

    def find_window(self, query: str):
        windows = self.list_windows(limit=300)
        wanted = self._normalized(query)
        exact = [item for item in windows if self._normalized(item.title) == wanted]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            candidates = ", ".join(f"{item.title!r} [{item.hwnd}]" for item in exact[:10])
            raise RuntimeError(
                f"Expected one exact window for {query!r}, found {len(exact)}: {candidates}"
            )

        containing = [
            item for item in windows if wanted and wanted in self._normalized(item.title)
        ]
        if len(containing) == 1:
            return containing[0]
        if len(containing) > 1:
            candidates = ", ".join(
                f"{item.title!r} [{item.hwnd}]" for item in containing[:10]
            )
            raise RuntimeError(
                f"Window target {query!r} is ambiguous; found {len(containing)} visible matches: "
                f"{candidates}. Use an exact title, process, or HWND."
            )

        scored = sorted(
            ((window_match_score(query, item), item) for item in windows),
            key=lambda pair: pair[0],
            reverse=True,
        )
        strong = [item for score, item in scored if score >= 72.0]
        if len(strong) == 1:
            return strong[0]
        nearest = ", ".join(
            f"{item.title!r} [{item.hwnd}]" for _score, item in scored[:7]
        ) or "none"
        if strong:
            raise RuntimeError(
                f"Window target {query!r} is ambiguous among {len(strong)} strong matches. "
                f"Candidates: {nearest}"
            )
        raise RuntimeError(f"No visible window matched {query!r}. Closest windows: {nearest}")

    def find_process_window(self, process: str):
        normalized = process.casefold().removesuffix(".exe")
        matches = [
            item
            for item in self.list_windows(limit=300)
            if (item.process_name or "").casefold().removesuffix(".exe") == normalized
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise RuntimeError(f"No visible window belongs to process {process!r}.")
        active = [item for item in matches if item.active]
        if len(active) == 1:
            return active[0]
        candidates = ", ".join(f"{item.title!r} [{item.hwnd}]" for item in matches[:12])
        raise RuntimeError(
            f"Process {process!r} has {len(matches)} visible windows and no unique active target: "
            f"{candidates}. Select an exact window title or HWND."
        )

    @staticmethod
    def desktop_locked() -> bool:
        try:
            import psutil
            import win32gui
            import win32process

            hwnd = int(win32gui.GetForegroundWindow())
            if not hwnd:
                return False
            _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid).name().casefold()
            title = (win32gui.GetWindowText(hwnd) or "").casefold()
            return (
                process in {"lockapp.exe", "logonui.exe"}
                or "windows default lock screen" in title
            )
        except Exception:
            return False

    def owned_windows(self, hwnd: int) -> list[dict[str, object]]:
        try:
            import win32con
            import win32gui
        except Exception:
            return []
        output: list[dict[str, object]] = []
        for item in self.list_windows(limit=300):
            if item.hwnd == hwnd:
                continue
            try:
                owner = int(win32gui.GetWindow(item.hwnd, win32con.GW_OWNER) or 0)
            except Exception:
                owner = 0
            if owner != hwnd:
                continue
            output.append(
                {
                    "hwnd": item.hwnd,
                    "title": item.title,
                    "process_id": item.process_id,
                    "process_name": item.process_name,
                    "active": item.active,
                    "rect": item.rect.model_dump(),
                }
            )
        return output

    def validate_bound_window(self, lease: Any) -> dict[str, object]:
        if self.desktop_locked():
            raise RuntimeError(
                "The Windows desktop is locked. Unlock it before Windows Agent continues."
            )
        if lease.bound_hwnd is None:
            return {"bound": False}
        current = self.window_by_hwnd(lease.bound_hwnd)
        if lease.bound_process and current.process_name:
            if current.process_name.casefold() != lease.bound_process.casefold():
                raise RuntimeError(
                    "The leased HWND now belongs to a different process. Input was blocked."
                )
        if lease.monitor_rect and current.rect.intersection_area(lease.monitor_rect) <= 0:
            raise RuntimeError(
                "The leased window moved outside the assigned monitor. Input was blocked."
            )
        return {
            "bound": True,
            "hwnd": current.hwnd,
            "title": current.title,
            "process_id": current.process_id,
            "process_name": current.process_name,
            "rect": current.rect.model_dump(),
            "owned_windows": self.owned_windows(current.hwnd),
        }


__all__ = ["WindowManager"]
