from __future__ import annotations

import platform

from agent_os.browser_precision_v3 import BrowserController
from agent_os.overlay import NullOverlay
from agent_os.overlay_hand import HandOverlay
from agent_os.runtime_v08 import DesktopAgent as BaseDesktopAgent
from agent_os.runtime_v08 import RunOutcome


class DesktopAgent(BaseDesktopAgent):
    """Form-aware runtime with selectable virtual or shared-system cursor display."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        previous_browser = self.browser
        self.browser = BrowserController(self.settings, self.cancellation)
        self.executor.browser = self.browser
        try:
            previous_browser.close(force=True)
        except Exception:
            pass

        previous_overlay = self.overlay
        self.overlay = (
            HandOverlay()
            if self.settings.overlay_enabled and platform.system() == "Windows"
            else NullOverlay()
        )
        self.executor.overlay = self.overlay
        try:
            previous_overlay.stop()
        except Exception:
            pass

    def set_overlay(self, enabled: bool) -> None:
        self.overlay.stop()
        self.settings.overlay_enabled = enabled
        self.overlay = (
            HandOverlay()
            if enabled and platform.system() == "Windows"
            else NullOverlay()
        )
        self.executor.overlay = self.overlay


__all__ = ["DesktopAgent", "RunOutcome"]
