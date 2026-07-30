from __future__ import annotations

from agent_os.capture_production import ScreenCapture
from agent_os.interaction_policy_production import InteractionPolicy
from agent_os.runtime_v11 import DesktopAgent as BaseDesktopAgent
from agent_os.runtime_v11 import RunOutcome
from agent_os.tools_production import ToolExecutor
from agent_os.windows_production import WindowManager


class DesktopAgent(BaseDesktopAgent):
    """Production runtime with observation-bound actions, safety, recovery, and metrics."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        previous_executor = self.executor

        self.windows = WindowManager()
        self.capture = ScreenCapture(self.settings, self.windows)
        self.interactions = InteractionPolicy()
        self.executor = ToolExecutor(
            self.settings,
            self.launcher,
            self.windows,
            self.browser,
            self.overlay,
            capture=self.capture,
            cancellation=self.cancellation,
            dry_run=previous_executor.dry_run,
            # Structured action-time confirmations are handled by InteractionPolicy.
            auto_confirm=True,
        )

    def _capture(self, lease, screenshot_path):
        self.capture.set_lease_generation(lease.generation)
        return super()._capture(lease, screenshot_path)

    def run(self, task: str, target_spec: str, *args, **kwargs) -> RunOutcome:
        if self.windows.desktop_locked():
            raise RuntimeError(
                "The Windows desktop is locked. Unlock it before starting Windows Agent."
            )
        self.interactions.reset()
        self.executor.configure_run(task)
        return super().run(task, target_spec, *args, **kwargs)


__all__ = ["DesktopAgent", "RunOutcome"]
