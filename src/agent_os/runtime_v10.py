from __future__ import annotations

import platform
from contextlib import suppress

from agent_os.browser_precision_v4 import BrowserController
from agent_os.overlay import NullOverlay
from agent_os.overlay_edges import EdgeOverlay
from agent_os.runtime_v08 import DesktopAgent as BaseDesktopAgent
from agent_os.runtime_v08 import RunOutcome
from agent_os.tools_controls import ToolExecutor


class DesktopAgent(BaseDesktopAgent):
    """Use in-page browser controls and an edge-only Windows focus overlay."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        previous_browser = self.browser
        previous_executor = self.executor
        self.browser = BrowserController(self.settings, self.cancellation)
        with suppress(Exception):
            previous_browser.close(force=True)

        previous_overlay = self.overlay
        self.overlay = (
            EdgeOverlay()
            if self.settings.overlay_enabled and platform.system() == "Windows"
            else NullOverlay()
        )
        with suppress(Exception):
            previous_overlay.stop()

        self.executor = ToolExecutor(
            self.settings,
            self.launcher,
            self.windows,
            self.browser,
            self.overlay,
            cancellation=self.cancellation,
            dry_run=previous_executor.dry_run,
            auto_confirm=previous_executor.auto_confirm,
        )

    def set_overlay(self, enabled: bool) -> None:
        self.overlay.stop()
        self.settings.overlay_enabled = enabled
        self.overlay = (
            EdgeOverlay()
            if enabled and platform.system() == "Windows"
            else NullOverlay()
        )
        self.executor.overlay = self.overlay


__all__ = ["DesktopAgent", "RunOutcome"]
