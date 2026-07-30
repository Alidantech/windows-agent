from __future__ import annotations

from agent_os.capture_runtime import ScreenCapture
from agent_os.dpi import enable_per_monitor_v2
from agent_os.lease import LeaseManager
from agent_os.models import ExecutionResult
from agent_os.runlog import RunLogger
from agent_os.runtime import DesktopAgent as BaseDesktopAgent, RunOutcome
from agent_os.targeting import task_allows_controller
from agent_os.task_contract import TaskContract
from agent_os.terminal_ui import ui


class DesktopAgent(BaseDesktopAgent):
    """Production runtime with task contracts and grounded visual observations."""

    def __init__(self, *args, **kwargs) -> None:
        enable_per_monitor_v2()
        super().__init__(*args, **kwargs)
        self.capture = ScreenCapture(self.settings, self.windows)

    def run(
        self,
        task: str,
        target_spec: str,
        max_steps: int | None = None,
        interactive: bool = True,
        ask_user=None,
        session_context=None,
        continue_browser: bool = False,
    ) -> RunOutcome:
        contract = TaskContract.from_task(task)
        if contract.navigation_only and contract.requested_url:
            return self._run_navigation_only(task, target_spec, contract)
        return super().run(
            task,
            target_spec,
            max_steps=max_steps,
            interactive=interactive,
            ask_user=ask_user,
            session_context=session_context,
            continue_browser=continue_browser,
        )

    def _run_navigation_only(
        self,
        task: str,
        target_spec: str,
        contract: TaskContract,
    ) -> RunOutcome:
        """Open the requested URL once and stop before any adjacent workflow."""

        self.cancellation.reset()
        controller = self.windows.active_window()
        allow_controller = task_allows_controller(task, target_spec, controller.title)
        self.executor.configure_controller(controller.hwnd, allow_controller)
        monitors = self.capture.list_monitors()
        lease_manager = LeaseManager(
            self.windows,
            monitors,
            controller,
            target_spec,
            self.settings.move_bound_window_to_monitor,
        )
        lease = lease_manager.lease
        logger = RunLogger(
            self.settings.runs_dir,
            task,
            target_spec,
            getattr(self.planner, "current_label", "auto"),
        )
        overlay_started = False
        if lease.monitor_rect:
            self.overlay.start(
                lease.monitor_rect,
                f"MONITOR {lease.monitor_index} · LEASE {lease.lease_id}",
            )
            self.overlay.status("NAVIGATING", "working")
            overlay_started = True

        logger.event(
            "run_started",
            summary=f"Navigation-only task started: {task}",
            controller=controller.model_dump(),
            controller_protected=not allow_controller,
            monitors=[item.model_dump() for item in monitors],
            control_lease=lease.as_dict(),
            task_contract={
                "navigation_only": True,
                "requested_url": contract.requested_url,
                "scope": contract.scope_summary,
            },
            settings=self._settings_summary(),
        )
        logger.update_manifest(
            control_lease=lease.as_dict(),
            settings=self._settings_summary(),
            task_contract={
                "navigation_only": True,
                "requested_url": contract.requested_url,
            },
        )
        ui.assistant(f"task {logger.run_id}: {task}")
        ui.notice(
            f"navigation contract · open {contract.requested_url} and stop",
            "cyan",
        )

        try:
            summary = self.browser.open_url(
                contract.requested_url,
                lease.monitor_rect,
                self.settings.browser_channel,
            )
            lease.bind_browser(
                self.browser.diagnostics().get("title") or "Isolated browser"
            )
            logger.update_manifest(control_lease=lease.as_dict())
            result = ExecutionResult(
                ok=True,
                summary=summary,
                details={"input": "browser-virtual", **self.browser.diagnostics()},
            )
            logger.event(
                "tool_result",
                summary=summary,
                step=1,
                result=result.model_dump(),
                control_lease=lease.as_dict(),
            )
            ui.action(
                1,
                1,
                "open_url",
                "Open the requested URL in the isolated browser and stop.",
            )
            ui.result(True, summary)

            screenshot = (
                logger.screenshot_path(1, "after")
                if self.settings.save_screenshots
                else None
            )
            observation = self.capture.capture_browser(
                self.browser,
                lease.monitor_index,
                screenshot_path=screenshot,
                lease_id=lease.lease_id,
            )
            logger.event(
                "observation",
                summary=f"Navigation destination: {observation.target.url}",
                step=1,
                capture_token=observation.capture_token,
                target=observation.target.model_dump(),
                control_lease=lease.as_dict(),
                screenshot=str(screenshot) if screenshot else None,
            )
            ui.observation(
                observation.target.label,
                "fresh navigation destination",
                screenshot,
            )

            if not contract.url_matches(observation.target.url):
                failure = (
                    f"Navigation ended at {observation.target.url!r}, which does not "
                    f"match the requested URL {contract.requested_url!r}."
                )
                logger.update_manifest(
                    status="failed",
                    steps=1,
                    summary=failure,
                    control_lease=lease.as_dict(),
                )
                self.overlay.status("URL MISMATCH", "error")
                return RunOutcome(False, failure, logger.run_id, str(logger.run_dir), 1)

            completion = (
                f"Opened {observation.target.url} in the isolated browser. "
                "Stopped at the requested destination without entering another workflow."
            )
            return self._complete(
                logger,
                lease,
                1,
                completion,
                "run_completed_by_task_contract",
            )
        except Exception as exc:
            logger.event(
                "run_crashed",
                summary=str(exc),
                error_type=type(exc).__name__,
            )
            logger.update_manifest(
                status="crashed",
                summary=str(exc),
                control_lease=lease.as_dict(),
            )
            self.overlay.status("CRASHED", "error")
            raise
        finally:
            if overlay_started:
                self.overlay.stop()


__all__ = ["DesktopAgent", "RunOutcome"]
