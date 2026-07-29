from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agent_os.apps import AppLauncher
from agent_os.browser_runtime import BrowserController
from agent_os.cancellation import AgentCancelled, CancellationToken
from agent_os.capture import CapturedObservation, ScreenCapture
from agent_os.config import Settings
from agent_os.lease import LeaseManager, TargetLease
from agent_os.models import AgentDecision, ExecutionResult
from agent_os.overlay import create_overlay
from agent_os.prompts import PromptBuilder
from agent_os.providers import RoutingPlanner
from agent_os.repeat import RepeatDetector
from agent_os.runlog import RunLogger
from agent_os.skills import SkillLoader
from agent_os.targeting import task_allows_controller
from agent_os.terminal_ui import ui
from agent_os.tools_runtime import ToolExecutor
from agent_os.windows import WindowManager


@dataclass(frozen=True)
class RunOutcome:
    success: bool
    summary: str
    run_id: str
    run_dir: str
    steps: int


class DesktopAgent:
    """Long-lived controller used by the persistent terminal session."""

    def __init__(self, settings: Settings, dry_run: bool = False, auto_confirm: bool = False) -> None:
        self.settings = settings
        self.cancellation = CancellationToken()
        self.windows = WindowManager()
        self.launcher = AppLauncher(settings.app_aliases_file, allow_unlisted=settings.allow_unlisted_apps)
        self.capture = ScreenCapture(settings, self.windows)
        self.prompts = PromptBuilder(settings.prompts_dir, self.launcher)
        self.skills = SkillLoader(settings.skills_dir)
        self.planner = self._new_planner()
        self.browser = BrowserController(settings, self.cancellation)
        self.overlay = create_overlay(settings.overlay_enabled)
        self.executor = ToolExecutor(
            settings, self.launcher, self.windows, self.browser, self.overlay,
            cancellation=self.cancellation, dry_run=dry_run, auto_confirm=auto_confirm,
        )

    def _new_planner(self) -> RoutingPlanner:
        return RoutingPlanner(self.settings, self.prompts, self.cancellation, event_sink=self._provider_event)

    def _provider_event(self, event: str, data: dict[str, object]) -> None:
        if event == "model_selected":
            ui.model_selected(str(data.get("route", "auto")))
        elif event == "model_fallback":
            ui.model_fallback(str(data.get("from", "model")), str(data.get("reason", "provider unavailable")), int(data.get("cooldown_seconds", 0)))
        elif event == "model_skipped":
            ui.notice(f"Skipped {data.get('route')}: {data.get('reason')}", "dim")

    def rebuild_planner(self) -> None:
        self.planner.close()
        self.planner = self._new_planner()

    def set_overlay(self, enabled: bool) -> None:
        self.overlay.stop()
        self.settings.overlay_enabled = enabled
        self.overlay = create_overlay(enabled)
        self.executor.overlay = self.overlay

    def request_stop(self) -> None:
        self.cancellation.cancel("Stopped by Ctrl+C.")
        self.browser.abort()

    def close(self, force: bool = False) -> None:
        self.overlay.stop()
        self.browser.close(force=force)
        self.planner.close()

    @staticmethod
    def _history(step: int, decision: AgentDecision, result: ExecutionResult | None) -> dict[str, Any]:
        return {"step": step, "decision": decision.model_dump(exclude_none=True), "result": result.model_dump() if result else None}

    @staticmethod
    def _annotation(decision: AgentDecision, observation: CapturedObservation) -> tuple[int | None, int | None]:
        if decision.x is not None and decision.y is not None:
            return decision.x, decision.y
        if decision.element_id:
            element = next((item for item in observation.uia.elements if item.element_id == decision.element_id), None)
            if element:
                return element.center_x, element.center_y
        return None, None

    def _capture(self, lease: TargetLease, screenshot_path: Any) -> CapturedObservation:
        if lease.backend == "browser":
            if not self.browser.active:
                raise RuntimeError("The leased browser session is closed.")
            return self.capture.capture_browser(self.browser, lease.monitor_index, screenshot_path=screenshot_path, lease_id=lease.lease_id)
        return self.capture.capture(lease.capture_spec, screenshot_path=screenshot_path, lease_id=lease.lease_id)

    def _settings_summary(self) -> dict[str, object]:
        return {
            "control_mode": self.settings.control_mode, "browser_backend": self.settings.browser_backend,
            "conflict_policy": self.settings.conflict_policy, "physical_input_policy": self.settings.physical_input_policy,
            "strict_capture_alignment": self.settings.strict_capture_alignment, "restore_user_cursor": self.settings.restore_user_cursor,
        }

    def _complete(self, logger: RunLogger, lease: TargetLease, step: int, summary: str, event: str = "run_completed") -> RunOutcome:
        logger.event(event, summary=summary, step=step)
        logger.update_manifest(status="completed", steps=step, summary=summary, control_lease=lease.as_dict())
        self.overlay.status("COMPLETED", "ready")
        return RunOutcome(True, summary, logger.run_id, str(logger.run_dir), step)

    def run(self, task: str, target_spec: str, max_steps: int | None = None, interactive: bool = True, ask_user: Callable[[str], str] | None = None, session_context: list[dict[str, object]] | None = None) -> RunOutcome:
        self.cancellation.reset()
        limit = max_steps or self.settings.max_steps
        logger = RunLogger(self.settings.runs_dir, task, target_spec, getattr(self.planner, "current_label", "auto"))
        repeat = RepeatDetector(self.settings.repeat_limit)
        skills = self.skills.select(task)
        history: list[dict[str, Any]] = []
        guidance: list[str] = []
        last_result: ExecutionResult | None = None
        rejected_done = 0
        controller = self.windows.active_window()
        allow_controller = task_allows_controller(task, target_spec, controller.title)
        self.executor.configure_controller(controller.hwnd, allow_controller)
        monitors = self.capture.list_monitors()
        lease_manager = LeaseManager(self.windows, monitors, controller, target_spec, self.settings.move_bound_window_to_monitor)
        lease = lease_manager.lease
        browser_terms = ("page", "website", "site", "browser", "link", "url", "tab", "form", "http", ".com", "scroll")
        if self.browser.active and (self.settings.control_mode == "browser" or any(term in task.lower() for term in browser_terms)):
            if lease.monitor_rect is None and self.browser.monitor_rect is not None:
                lease.monitor_rect = self.browser.monitor_rect
                lease.monitor_index = self.windows.monitor_for_rect(self.browser.monitor_rect, [(item.index, item.rect) for item in monitors])
            lease.bind_browser(self.browser.diagnostics().get("title") or "Isolated browser")
        overlay_started = False
        if lease.monitor_rect:
            self.overlay.start(lease.monitor_rect, f"MONITOR {lease.monitor_index} · LEASE {lease.lease_id}")
            self.overlay.status("ASSIGNED", "ready")
            overlay_started = True
        logger.event("run_started", summary=f"Task started: {task}", controller=controller.model_dump(), controller_protected=not allow_controller, monitors=[item.model_dump() for item in monitors], control_lease=lease.as_dict(), settings=self._settings_summary(), selected_skills=[item.name for item in skills])
        logger.update_manifest(control_lease=lease.as_dict(), settings=self._settings_summary())
        ui.assistant(f"task {logger.run_id}: {task}")
        ui.notice(f"{len(monitors)} monitors · {lease.label()} · {self.settings.control_mode}", "dim")
        lease_generation = lease.generation
        try:
            for step in range(1, limit + 1):
                self.cancellation.raise_if_cancelled()
                if lease.backend == "desktop" and lease.bound_hwnd:
                    lease_manager.refresh()
                screenshot = logger.screenshot_path(step, "before") if self.settings.save_screenshots else None
                observation = self._capture(lease, screenshot)
                if lease.backend == "desktop" and lease.bound_hwnd and observation.target.hwnd != lease.bound_hwnd:
                    raise RuntimeError("Screenshot/control mismatch: captured HWND differs from the lease.")
                if lease.backend == "browser" and observation.target.backend != "browser":
                    raise RuntimeError("Screenshot/control mismatch: browser lease produced desktop pixels.")
                ui.observation(observation.target.label, f"{observation.target.capture_source} · monitor {observation.target.monitor_index or '-'}", screenshot)
                logger.event("observation", summary=f"Captured step {step}: {observation.target.label}", step=step, capture_token=observation.capture_token, target=observation.target.model_dump(), control_lease=lease.as_dict(), screenshot=str(screenshot) if screenshot else None)
                prompt = self.prompts.build_step_prompt(task, step, observation, lease, skills, history, last_result, guidance, controller, not allow_controller, self._settings_summary(), session_context=session_context)
                with ui.thinking("Planning next action…"):
                    decision, raw = self.planner.plan(prompt, observation.api_image_bytes)
                logger.event("model_decision", summary=f"Step {step}: {decision.action} — {decision.reason}", step=step, decision=decision.model_dump(exclude_none=True), raw_response=raw, capture_token=observation.capture_token, control_lease=lease.as_dict())
                ui.action(step, limit, decision.action, decision.reason)
                if decision.action == "ask_user":
                    if not interactive:
                        summary = decision.message or "User input required."
                        logger.update_manifest(status="needs_input", steps=step, summary=summary)
                        return RunOutcome(False, summary, logger.run_id, str(logger.run_dir), step)
                    question = decision.message or "The agent needs guidance."
                    answer = ask_user(question) if ask_user else input(question + " ")
                    guidance.append(answer)
                    last_result = ExecutionResult(ok=True, summary=f"User guidance: {answer}")
                    history.append(self._history(step, decision, last_result))
                    continue
                if decision.action == "fail":
                    summary = decision.message or decision.reason
                    logger.update_manifest(status="failed", steps=step, summary=summary)
                    return RunOutcome(False, summary, logger.run_id, str(logger.run_dir), step)
                if decision.action == "done":
                    rejection = None
                    hint = None
                    if last_result is not None and not last_result.ok:
                        rejection, hint = "The immediately preceding action failed.", "Recover before declaring completion."
                    elif self.settings.verify_done:
                        verify_prompt = self.prompts.build_verifier_prompt(task, observation, lease, decision.reason, controller, not allow_controller)
                        with ui.thinking("Verifying completion…"):
                            verification, verify_raw = self.planner.verify(verify_prompt, observation.api_image_bytes)
                        logger.event("completion_verification", summary=verification.evidence, step=step, verification=verification.model_dump(), raw_response=verify_raw)
                        if not verification.complete:
                            rejection = verification.evidence
                            hint = verification.next_hint or "Inspect the leased target again."
                    if rejection:
                        rejected_done += 1
                        rejected = ExecutionResult(ok=False, summary=f"Completion rejected: {rejection}")
                        history.append(self._history(step, decision, rejected))
                        ui.result(False, rejection, label="NOT DONE")
                        if hint:
                            ui.notice(f"next: {hint}")
                        if rejected_done >= 2:
                            guidance.append("Completion was rejected repeatedly. Change strategy and require exact evidence.")
                        continue
                    return self._complete(logger, lease, step, decision.message or decision.reason)
                if repeat.add(decision.signature()) >= self.settings.repeat_limit:
                    last_result = ExecutionResult(ok=False, summary=f"Blocked repeated {decision.action} action.")
                    history.append(self._history(step, decision, last_result))
                    ui.result(False, last_result.summary, label="BLOCKED")
                    continue
                x, y = self._annotation(decision, observation)
                if self.settings.save_screenshots:
                    ScreenCapture.annotate_action(observation.original_image, decision.action, x, y, logger.screenshot_path(step, "action"))
                before_windows = observation.windows
                result = self.executor.execute(decision, observation, lease, logger.run_dir)
                changed, label = lease_manager.discover_after_action(decision, result, before_windows)
                if lease.backend == "browser" and not overlay_started and lease.monitor_rect:
                    self.overlay.start(lease.monitor_rect, f"MONITOR {lease.monitor_index} · LEASE {lease.lease_id}")
                    overlay_started = True
                if changed or lease.generation != lease_generation:
                    lease_generation = lease.generation
                    ui.result(True, label or lease.label(), label="BOUND")
                    logger.update_manifest(control_lease=lease.as_dict())
                last_result = result
                history.append(self._history(step, decision, result))
                logger.event("tool_result", summary=result.summary, step=step, result=result.model_dump(), control_lease=lease.as_dict())
                ui.result(result.ok, result.summary)
                if result.ok and result.task_complete:
                    logger.update_manifest(completion_evidence=result.completion_evidence, control_lease=lease.as_dict())
                    ui.notice("deterministic tool evidence accepted", "green")
                    return self._complete(logger, lease, step, result.summary, "run_completed_by_tool")
                if self.cancellation.wait(self.settings.step_delay_seconds):
                    self.cancellation.raise_if_cancelled()
            summary = f"Maximum step limit ({limit}) reached before completion."
            logger.update_manifest(status="max_steps", steps=limit, summary=summary)
            self.overlay.status("MAX STEPS", "error")
            return RunOutcome(False, summary, logger.run_id, str(logger.run_dir), limit)
        except AgentCancelled:
            logger.event("run_interrupted", summary="Stopped by Ctrl+C.")
            logger.update_manifest(status="interrupted", control_lease=lease.as_dict())
            self.overlay.status("STOPPED", "stopped")
            raise
        except KeyboardInterrupt:
            logger.event("run_interrupted", summary="Stopped by Ctrl+C.")
            logger.update_manifest(status="interrupted", control_lease=lease.as_dict())
            self.overlay.status("STOPPED", "error")
            raise
        except Exception as exc:
            logger.event("run_crashed", summary=str(exc), error_type=type(exc).__name__)
            logger.update_manifest(status="crashed", summary=str(exc), control_lease=lease.as_dict())
            self.overlay.status("CRASHED", "error")
            raise
        finally:
            self.overlay.stop()
