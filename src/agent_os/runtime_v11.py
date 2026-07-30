from __future__ import annotations

from contextlib import suppress

from agent_os.browser_semantic_runtime import BrowserController
from agent_os.runtime_v10 import DesktopAgent as BaseDesktopAgent
from agent_os.runtime_v10 import RunOutcome
from agent_os.tools_controls import ToolExecutor


class DesktopAgent(BaseDesktopAgent):
    """Use stable semantic browser handles and visible live self-healing locators."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        previous_browser = self.browser
        previous_executor = self.executor
        self.browser = BrowserController(self.settings, self.cancellation)
        with suppress(Exception):
            previous_browser.close(force=True)

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


__all__ = ["DesktopAgent", "RunOutcome"]
