from __future__ import annotations

from agent_os.browser_precision_v2 import BrowserController
from agent_os.runtime_v07 import DesktopAgent as BaseDesktopAgent
from agent_os.runtime_v07 import RunOutcome


class DesktopAgent(BaseDesktopAgent):
    """Grounded runtime using the DPI-safe precision browser controller."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        previous = self.browser
        self.browser = BrowserController(self.settings, self.cancellation)
        self.executor.browser = self.browser
        try:
            previous.close(force=True)
        except Exception:
            pass


__all__ = ["DesktopAgent", "RunOutcome"]
