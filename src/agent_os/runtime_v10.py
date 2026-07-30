from __future__ import annotations

import platform
from contextlib import suppress

from agent_os.browser_precision_v4 import BrowserController
from agent_os.overlay import NullOverlay
from agent_os.overlay_edges import EdgeOverlay
from agent_os.runtime_v08 import DesktopAgent as BaseDesktopAgent
from agent_os.runtime_v08 import RunOutcome


class DesktopAgent(BaseDesktopAgent):
    """Use an in-page browser cursor and an edge-only Windows focus overlay."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        previous_browser = self.browser
        self.browser = BrowserController(self.settings, self.cancellation)
        self.executor.browser = self.browser
        with suppress(Exception):
            previous_browser.close(force=True)

        previous_overlay = self.overlay
        self.overlay = (
            EdgeOverlay()
            if self.settings.overlay_enabled and platform.system() == "Windows"
            else NullOverlay()
        )
        self.executor.overlay = self.overlay
        with suppress(Exception):
            previous_overlay.stop()

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
