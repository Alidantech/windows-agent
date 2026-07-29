from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.prompt import Prompt

from agent_os.apps import AppLauncher
from agent_os.browser import BrowserController
from agent_os.capture import CapturedObservation, ScreenCapture
from agent_os.config import Settings
from agent_os.lease import LeaseManager, TargetLease
from agent_os.models import AgentDecision, ExecutionResult
from agent_os.overlay import create_overlay
from agent_os.prompts import PromptBuilder
from agent_os.provider import GeminiPlanner
from agent_os.repeat import RepeatDetector
from agent_os.runlog import RunLogger
from agent_os.skills import SkillLoader
from agent_os.targeting import task_allows_controller
from agent_os.tools import ToolExecutor
from agent_os.windows import WindowManager

console = Console()


@dataclass(frozen=True)
class RunOutcome:
    success: bool
    summary: str
    run_id: str
    run_dir: str
    steps: int


class DesktopAgent:
    def __init__(
        self,
        settings: Settings,
        dry_run: bool = False,
        auto_confirm: bool = False,
    ) -> None:
        self.settings = settings
        self.windows = WindowManager()
        self.launcher = AppLauncher(
            settings.app_aliases_file,
            allow_unlisted=settings.allow_unlisted_apps,
        )
        self.capture = ScreenCapture(settings, self.windows)
        self.prompts = PromptBuilder(settings.prompts_dir, self.launcher)
        self.skills = SkillLoader(settings.skills_dir)
        self.planner = GeminiPlanner(settings, self.prompts)
        self.browser = BrowserController(settings)
        self.overlay = create_overlay(settings.overlay_enabled)
        self.executor = ToolExecutor(
            settings,
            self.launcher,
            self.windows,
            self.browser,
            self.overlay,
            dry_run=dry_run,
            auto_confirm=auto_confirm,
        )

    def close(self) -> None:
        self.overlay.stop()
        self.browser.close()

    @staticmethod
    def _history_item(
        step: int,
        decision: AgentDecision,
        result: ExecutionResult | None,
    ) -> dict[str, Any]:
        return {
            "step": step,
            "decision": decision.model_dump(exclude_none=True),
            "result": result.model_dump() if result else None,
        }

    @staticmethod
    def _annotation_coordinates(
        decision: AgentDecision,
        observation: CapturedObservation,
    ) -> tuple[int | None, int | None]:
        if decision.x is not None and decision.y is not None:
            return decision.x, decision.y
        if decision.element_id:
            element = next(
                (item for item in observation.uia.elements if item.element_id == decision.element_id),
                None,
            )
            if element:
                return element.center_x, element.center_y
        return None, None

    def _capture(
        self,
        lease: TargetLease,
        screenshot_path: Any,
    ) -> CapturedObservation:
        if lease.backend == "browser":
            if not self.browser.active:
                raise RuntimeError("The control lease is browser-backed, but the browser session is closed.")
            return self.capture.capture_browser(
                self.browser,
                lease.monitor_index,
                screenshot_path=screenshot_path,
                lease_id=lease.lease_id,
            )
        return self.capture.capture(
            lease.capture_spec,
            screenshot_path=screenshot_path,
            lease_id=lease.lease_id,
        )

    def _settings_summary(self) -> dict[str, object]:
        return {
            "control_mode": self.settings.control_mode,
            "browser_backend": self.settings.browser_backend,
            "conflict_policy": self.settings.conflict_policy,
            "physical_input_policy": self.settings.physical_input_policy,
            "strict_capture_alignment": self.settings.strict_capture_alignment,
            "restore_user_cursor": self.settings.restore_user_cursor,
        }

    def run(
        self,
        task: str,
        target_spec: str,
        max_steps: int | None = None,
        interactive: bool = True,
    ) -> RunOutcome:
        limit = max_steps or self.settings.max_steps
        logger = RunLogger(self.settings.runs_dir, task, target_spec, self.settings.model)
        repeat = RepeatDetector(self.settings.repeat_limit)
        selected_skills = self.skills.select(task)
        history: list[dict[str, Any]] = []
        guidance: list[str] = []
        last_result: ExecutionResult | None = None
        stuck_count = 0
        rejected_done_count = 0

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
        selected_skill_names = {item.name for item in selected_skills}
        browser_continuation_terms = (
            "page", "website", "site", "browser", "link", "url", "tab", "form",
            "chatgpt", "http", ".com", "scroll", "current page",
        )
        continue_browser = (
            self.browser.active
            and (
                self.settings.control_mode == "browser"
                or "browser" in selected_skill_names
                or "smoke-testing" in selected_skill_names
                or any(term in task.lower() for term in browser_continuation_terms)
            )
        )
        if continue_browser:
            if lease.monitor_rect is None and self.browser.monitor_rect is not None:
                lease.monitor_rect = self.browser.monitor_rect
                pairs = [(item.index, item.rect) for item in monitors]
                lease.monitor_index = self.windows.monitor_for_rect(
                    self.browser.monitor_rect, pairs
                )
            lease.bind_browser(self.browser.diagnostics().get("title") or "Isolated browser")
        logged_lease_generation = lease.generation
        overlay_started = False
        if lease.monitor_rect:
            self.overlay.start(
                lease.monitor_rect,
                f"MONITOR {lease.monitor_index} · LEASE {lease.lease_id}",
            )
            self.overlay.status("ASSIGNED", "ready")
            overlay_started = True

        logger.event(
            "run_started",
            summary=f"Task started: {task}",
            controller=controller.model_dump(),
            controller_protected=not allow_controller,
            monitors=[item.model_dump() for item in monitors],
            control_lease=lease.as_dict(),
            settings=self._settings_summary(),
            selected_skills=[item.name for item in selected_skills],
        )
        logger.update_manifest(
            control_lease=lease.as_dict(),
            settings=self._settings_summary(),
        )

        console.print(f"[bold cyan]Run:[/bold cyan] {logger.run_id}")
        console.print(f"[bold]Task:[/bold] {task}")
        console.print(f"[bold]Requested target:[/bold] {target_spec}")
        console.print(f"[bold]Detected monitors:[/bold] {len(monitors)}")
        if lease.monitor_rect:
            rect = lease.monitor_rect
            console.print(
                f"[bold]Assigned monitor:[/bold] {lease.monitor_index} "
                f"({rect.width}x{rect.height} at {rect.left},{rect.top})"
            )
        console.print(f"[bold]Control lease:[/bold] {lease.label()}")
        console.print(
            f"[bold]Control mode:[/bold] {self.settings.control_mode}; "
            f"browser={self.settings.browser_backend}; conflicts={self.settings.conflict_policy}; "
            f"physical input={self.settings.physical_input_policy}"
        )
        if not allow_controller:
            console.print(
                f"[bold]Protected controller:[/bold] {controller.title} "
                "(the lease cannot bind to this console)"
            )
        console.print("Emergency stop: move the pointer to the top-left corner or press Ctrl+C.\n")

        try:
            for step in range(1, limit + 1):
                if lease.backend == "desktop" and lease.bound_hwnd:
                    lease_manager.refresh()
                screenshot_path = (
                    logger.screenshot_path(step, "before")
                    if self.settings.save_screenshots
                    else None
                )
                observation = self._capture(lease, screenshot_path)
                if lease.backend == "desktop" and lease.bound_hwnd:
                    if observation.target.hwnd != lease.bound_hwnd:
                        raise RuntimeError(
                            "Internal alignment failure: captured HWND differs from the control lease."
                        )
                if lease.backend == "browser" and observation.target.backend != "browser":
                    raise RuntimeError("Internal alignment failure: browser lease produced desktop pixels.")

                console.print(
                    f"[dim]Seeing controlled target: {observation.target.label} · "
                    f"backend={observation.target.backend} · "
                    f"source={observation.target.capture_source} · "
                    f"monitor={observation.target.monitor_index or '-'} · "
                    f"identity={observation.target.identity} "
                    f"({observation.original_image.width}x{observation.original_image.height})"
                    + (f" | {screenshot_path}" if screenshot_path else "")
                    + "[/dim]"
                )
                self.overlay.status(f"STEP {step} · OBSERVING", "working")
                logger.event(
                    "observation",
                    summary=f"Captured step {step}: {observation.target.label}",
                    step=step,
                    capture_token=observation.capture_token,
                    control_lease=lease.as_dict(),
                    target=observation.target.model_dump(),
                    observation_state=observation.state,
                    screenshot=str(screenshot_path) if screenshot_path else None,
                    visible_windows=[item.model_dump() for item in observation.windows],
                    ui_elements=[item.model_dump() for item in observation.uia.elements],
                )

                prompt = self.prompts.build_step_prompt(
                    task,
                    step,
                    observation,
                    lease,
                    selected_skills,
                    history,
                    last_result,
                    guidance,
                    controller,
                    not allow_controller,
                    self._settings_summary(),
                )
                decision, raw = self.planner.plan(prompt, observation.api_image_bytes)
                logger.event(
                    "model_decision",
                    summary=f"Step {step}: {decision.action} — {decision.reason}",
                    step=step,
                    decision=decision.model_dump(exclude_none=True),
                    raw_response=raw,
                    capture_token=observation.capture_token,
                    control_lease=lease.as_dict(),
                )
                console.print(
                    f"[bold]Step {step}/{limit}[/bold] [cyan]{decision.action}[/cyan]: "
                    f"{decision.reason}"
                )

                if decision.action == "ask_user":
                    self.overlay.status("USER INPUT REQUIRED", "question")
                    if not interactive:
                        summary = decision.message or "Agent requested user input."
                        logger.update_manifest(status="needs_input", steps=step, summary=summary)
                        return RunOutcome(False, summary, logger.run_id, str(logger.run_dir), step)
                    try:
                        answer = Prompt.ask(decision.message or "The agent needs guidance")
                    except EOFError:
                        logger.update_manifest(status="input_closed", steps=step)
                        return RunOutcome(
                            False,
                            "Input stream closed while waiting for guidance.",
                            logger.run_id,
                            str(logger.run_dir),
                            step,
                        )
                    guidance.append(answer)
                    last_result = ExecutionResult(ok=True, summary=f"User guidance: {answer}")
                    history.append(self._history_item(step, decision, last_result))
                    logger.event("user_guidance", summary=answer, step=step)
                    repeat.clear()
                    continue

                if decision.action == "fail":
                    summary = decision.message or decision.reason
                    logger.event("run_failed", summary=summary, step=step)
                    logger.update_manifest(status="failed", steps=step, summary=summary)
                    self.overlay.status("FAILED", "error")
                    return RunOutcome(False, summary, logger.run_id, str(logger.run_dir), step)

                if decision.action == "done":
                    rejection: str | None = None
                    hint: str | None = None
                    if last_result is not None and not last_result.ok:
                        rejection = "The immediately preceding action failed."
                        hint = "Recover before declaring completion."
                    elif self.settings.verify_done:
                        verify_prompt = self.prompts.build_verifier_prompt(
                            task,
                            observation,
                            lease,
                            decision.reason,
                            controller,
                            not allow_controller,
                        )
                        verification, verify_raw = self.planner.verify(
                            verify_prompt,
                            observation.api_image_bytes,
                        )
                        logger.event(
                            "completion_verification",
                            summary=verification.evidence,
                            step=step,
                            verification=verification.model_dump(),
                            raw_response=verify_raw,
                        )
                        if not verification.complete:
                            rejection = verification.evidence
                            hint = verification.next_hint or "Inspect the controlled target again."
                    if rejection:
                        rejected_done_count += 1
                        last_result = ExecutionResult(
                            ok=False,
                            summary=f"Completion rejected: {rejection} Hint: {hint}",
                        )
                        history.append(self._history_item(step, decision, last_result))
                        logger.event(
                            "completion_rejected",
                            summary=last_result.summary,
                            step=step,
                        )
                        console.print(f"  [yellow]NOT DONE:[/yellow] {rejection}")
                        if hint:
                            console.print(f"  [yellow]Next:[/yellow] {hint}")
                        if rejected_done_count >= 2:
                            guidance.append(
                                "Completion was rejected repeatedly. Change strategy and require exact evidence."
                            )
                        continue
                    summary = decision.message or decision.reason
                    logger.event("run_completed", summary=summary, step=step)
                    logger.update_manifest(
                        status="completed",
                        steps=step,
                        summary=summary,
                        control_lease=lease.as_dict(),
                    )
                    self.overlay.status("COMPLETED", "ready")
                    return RunOutcome(True, summary, logger.run_id, str(logger.run_dir), step)

                count = repeat.add(decision.signature())
                if count >= self.settings.repeat_limit:
                    stuck_count += 1
                    last_result = ExecutionResult(
                        ok=False,
                        summary=(
                            f"Stuck detector blocked repeated {decision.action} action {count} times."
                        ),
                    )
                    history.append(self._history_item(step, decision, last_result))
                    logger.event("stuck_detected", summary=last_result.summary, step=step)
                    console.print(f"  [yellow]BLOCKED:[/yellow] {last_result.summary}")
                    if stuck_count >= 2:
                        if not interactive:
                            logger.update_manifest(status="stopped_stuck", steps=step)
                            return RunOutcome(
                                False,
                                "Stopped after repeated actions.",
                                logger.run_id,
                                str(logger.run_dir),
                                step,
                            )
                        try:
                            answer = Prompt.ask(
                                "Agent is stuck. Give guidance, or type STOP",
                                default="STOP",
                            )
                        except EOFError:
                            answer = "STOP"
                        if answer.strip().upper() == "STOP":
                            logger.update_manifest(status="stopped_stuck", steps=step)
                            return RunOutcome(
                                False,
                                "Stopped after repeated actions.",
                                logger.run_id,
                                str(logger.run_dir),
                                step,
                            )
                        guidance.append(answer)
                        repeat.clear()
                        stuck_count = 0
                    continue

                x, y = self._annotation_coordinates(decision, observation)
                if self.settings.save_screenshots:
                    ScreenCapture.annotate_action(
                        observation.original_image,
                        decision.action,
                        x,
                        y,
                        logger.screenshot_path(step, "action"),
                    )

                before_windows = observation.windows
                result = self.executor.execute(
                    decision,
                    observation,
                    lease,
                    logger.run_dir,
                )
                changed, lease_label = lease_manager.discover_after_action(
                    decision,
                    result,
                    before_windows,
                )
                if lease.backend == "browser" and not overlay_started and lease.monitor_rect:
                    self.overlay.start(
                        lease.monitor_rect,
                        f"MONITOR {lease.monitor_index} · LEASE {lease.lease_id}",
                    )
                    overlay_started = True
                lease_generation_changed = lease.generation != logged_lease_generation
                if changed or lease_generation_changed:
                    logged_lease_generation = lease.generation
                    console.print(f"  [magenta]BOUND:[/magenta] {lease.label()}")
                    logger.event(
                        "lease_bound",
                        summary=lease_label or lease.label(),
                        step=step,
                        control_lease=lease.as_dict(),
                    )
                    logger.update_manifest(control_lease=lease.as_dict())

                last_result = result
                history.append(self._history_item(step, decision, result))
                logger.event(
                    "tool_result",
                    summary=result.summary,
                    step=step,
                    result=result.model_dump(),
                    control_lease=lease.as_dict(),
                )
                console.print(
                    f"  {'[green]OK[/green]' if result.ok else '[red]FAILED[/red]'}: {result.summary}"
                )
                if result.ok:
                    stuck_count = 0
                time.sleep(self.settings.step_delay_seconds)

            summary = f"Maximum step limit ({limit}) reached before completion."
            logger.event("run_failed", summary=summary, step=limit)
            logger.update_manifest(status="max_steps", steps=limit, summary=summary)
            self.overlay.status("MAX STEPS", "error")
            return RunOutcome(False, summary, logger.run_id, str(logger.run_dir), limit)
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
