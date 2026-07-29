from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.prompt import Prompt

from agent_os.apps import AppLauncher
from agent_os.capture import CapturedObservation, ScreenCapture
from agent_os.config import Settings
from agent_os.models import AgentDecision, ExecutionResult, WindowInfo
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
        self.window_manager = WindowManager()
        self.app_launcher = AppLauncher(
            settings.app_aliases_file,
            allow_unlisted=settings.allow_unlisted_apps,
        )
        self.capture = ScreenCapture(settings, self.window_manager)
        self.prompts = PromptBuilder(settings.prompts_dir, self.app_launcher)
        self.skills = SkillLoader(settings.skills_dir)
        self.planner = GeminiPlanner(settings, self.prompts)
        self.executor = ToolExecutor(
            settings,
            self.app_launcher,
            self.window_manager,
            dry_run=dry_run,
            auto_confirm=auto_confirm,
        )

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
        if decision.action == "click_element" and decision.element_id:
            element = next(
                (item for item in observation.uia.elements if item.element_id == decision.element_id),
                None,
            )
            if element:
                return element.center_x, element.center_y
        return None, None

    def _effective_target(
        self,
        requested_target: str,
        controller: WindowInfo,
        allow_controller: bool,
    ) -> tuple[str, bool]:
        lowered = requested_target.strip().lower()
        if lowered not in {"active", "active-window"} or allow_controller:
            return requested_target, False
        try:
            if self.window_manager.active_hwnd() == controller.hwnd:
                return "desktop", True
        except Exception:
            pass
        return requested_target, False

    def _restore_after_prompt(self, hwnd: int | None, controller_hwnd: int) -> None:
        if hwnd is None or hwnd == controller_hwnd:
            return
        try:
            self.window_manager.activate_hwnd(hwnd)
            time.sleep(0.3)
        except Exception:
            # The window may have closed while the user was answering.
            pass

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

        controller = self.window_manager.active_window()
        allow_controller = task_allows_controller(task, target_spec, controller.title)
        self.executor.configure_controller(controller.hwnd, allow_controller)

        logger.event(
            "run_started",
            summary=f"Task started: {task}",
            selected_skills=[skill.name for skill in selected_skills],
            controller={
                "hwnd": controller.hwnd,
                "title": controller.title,
                "process_name": controller.process_name,
                "protected": not allow_controller,
            },
        )
        console.print(f"[bold cyan]Run:[/bold cyan] {logger.run_id}")
        console.print(f"[bold]Task:[/bold] {task}")
        console.print(f"[bold]Requested target:[/bold] {target_spec}")
        if not allow_controller:
            console.print(
                f"[bold]Protected controller:[/bold] {controller.title} "
                "(the agent will not type or click into its own console)"
            )
        console.print("Emergency stop: move the pointer to the top-left corner or press Ctrl+C.\n")

        try:
            for step in range(1, limit + 1):
                effective_target, discovery_mode = self._effective_target(
                    target_spec,
                    controller,
                    allow_controller,
                )
                screenshot_path = (
                    logger.screenshot_path(step, "before")
                    if self.settings.save_screenshots
                    else None
                )
                observation = self.capture.capture(effective_target, screenshot_path=screenshot_path)
                if discovery_mode:
                    console.print(
                        "[yellow]Controller console is foreground; observing the desktop to select "
                        "the real destination window.[/yellow]"
                    )
                console.print(
                    f"[dim]Seeing: {observation.target.label} "
                    f"({observation.original_image.width}x{observation.original_image.height})"
                    + (f" | {screenshot_path}" if screenshot_path else "")
                    + "[/dim]"
                )
                logger.event(
                    "observation",
                    summary=f"Captured step {step}: {observation.target.label}",
                    step=step,
                    requested_target=target_spec,
                    effective_target=effective_target,
                    discovery_mode=discovery_mode,
                    target=observation.target.model_dump(),
                    screenshot=str(screenshot_path) if screenshot_path else None,
                    monitors=[item.model_dump() for item in observation.monitors],
                    visible_windows=[
                        {
                            "title": item.title,
                            "process_name": item.process_name,
                            "active": item.active,
                            "rect": item.rect.model_dump(),
                        }
                        for item in observation.windows
                    ],
                    ui_elements=[item.model_dump() for item in observation.uia.elements],
                    ui_element_count=len(observation.uia.elements),
                )

                prompt = self.prompts.build_step_prompt(
                    task=task,
                    step=step,
                    observation=observation,
                    skills=selected_skills,
                    history=history,
                    last_result=last_result,
                    user_guidance=guidance,
                    requested_target=target_spec,
                    controller_window=controller,
                    controller_protected=not allow_controller,
                )
                decision, raw = self.planner.plan(prompt, observation.api_image_bytes)
                logger.event(
                    "model_decision",
                    summary=f"Step {step}: {decision.action} — {decision.reason}",
                    step=step,
                    decision=decision.model_dump(exclude_none=True),
                    raw_response=raw,
                )
                console.print(
                    f"[bold]Step {step}/{limit}[/bold] [cyan]{decision.action}[/cyan]: "
                    f"{decision.reason}"
                )

                if decision.action == "ask_user":
                    if not interactive:
                        outcome = RunOutcome(
                            False,
                            decision.message or "Agent requested user input.",
                            logger.run_id,
                            str(logger.run_dir),
                            step,
                        )
                        logger.update_manifest(status="needs_input", steps=step)
                        return outcome
                    return_hwnd = observation.target.hwnd
                    try:
                        answer = Prompt.ask(decision.message or "The agent needs guidance")
                    except EOFError:
                        logger.update_manifest(status="input_closed", steps=step)
                        return RunOutcome(
                            False,
                            "Input stream closed while the agent was waiting for guidance.",
                            logger.run_id,
                            str(logger.run_dir),
                            step,
                        )
                    guidance.append(answer)
                    last_result = ExecutionResult(ok=True, summary=f"User guidance: {answer}")
                    history.append(self._history_item(step, decision, last_result))
                    logger.event("user_guidance", summary=answer, step=step)
                    repeat.clear()
                    self._restore_after_prompt(return_hwnd, controller.hwnd)
                    continue

                if decision.action == "fail":
                    summary = decision.message or decision.reason
                    logger.event("run_failed", summary=summary, step=step)
                    logger.update_manifest(status="failed", steps=step, summary=summary)
                    return RunOutcome(False, summary, logger.run_id, str(logger.run_dir), step)

                if decision.action == "done":
                    rejection: str | None = None
                    next_hint: str | None = None
                    if last_result is not None and not last_result.ok:
                        rejection = "The immediately preceding action failed, so completion cannot be accepted."
                        next_hint = "Recover from the failed action before declaring completion."
                    elif (
                        not allow_controller
                        and observation.target.hwnd is not None
                        and observation.target.hwnd == controller.hwnd
                    ):
                        rejection = "The visible window is the protected Agent OS controller, not the destination application."
                        next_hint = "Activate or open the intended destination window first."
                    elif self.settings.verify_done:
                        verify_prompt = self.prompts.build_verifier_prompt(
                            task,
                            observation,
                            decision.reason,
                            requested_target=target_spec,
                            controller_window=controller,
                            controller_protected=not allow_controller,
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
                            next_hint = verification.next_hint or "Inspect the destination again."

                    if rejection is not None:
                        rejected_done_count += 1
                        last_result = ExecutionResult(
                            ok=False,
                            summary=f"Completion rejected: {rejection} Hint: {next_hint}",
                        )
                        history.append(self._history_item(step, decision, last_result))
                        logger.event(
                            "completion_rejected",
                            summary=last_result.summary,
                            step=step,
                            rejected_done_count=rejected_done_count,
                        )
                        console.print(f"  [yellow]NOT DONE:[/yellow] {rejection}")
                        if next_hint:
                            console.print(f"  [yellow]Next:[/yellow] {next_hint}")
                        if rejected_done_count >= 2:
                            guidance.append(
                                "Completion was rejected repeatedly. Do not return done again until visible "
                                "evidence proves the exact requested result. Change strategy or ask the user."
                            )
                        repeat.add(f"rejected_done|{decision.signature()}")
                        continue

                    summary = decision.message or decision.reason
                    logger.event("run_completed", summary=summary, step=step)
                    logger.update_manifest(status="completed", steps=step, summary=summary)
                    return RunOutcome(True, summary, logger.run_id, str(logger.run_dir), step)

                signature_count = repeat.add(decision.signature())
                if signature_count >= self.settings.repeat_limit:
                    stuck_count += 1
                    last_result = ExecutionResult(
                        ok=False,
                        summary=(
                            f"Stuck detector blocked repeated action {decision.action} "
                            f"{signature_count} times. Choose a different semantic tool, inspect UI elements, "
                            "change windows, or ask the user."
                        ),
                    )
                    logger.event(
                        "stuck_detected",
                        summary=last_result.summary,
                        step=step,
                        decision=decision.model_dump(exclude_none=True),
                    )
                    history.append(self._history_item(step, decision, last_result))
                    console.print(f"  [yellow]BLOCKED:[/yellow] {last_result.summary}")
                    if stuck_count >= 2:
                        if interactive:
                            try:
                                answer = Prompt.ask(
                                    "Agent is still stuck. Give guidance, or type STOP",
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
                        else:
                            logger.update_manifest(status="stopped_stuck", steps=step)
                            return RunOutcome(
                                False,
                                "Stopped after repeated actions.",
                                logger.run_id,
                                str(logger.run_dir),
                                step,
                            )
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

                result = self.executor.execute(decision, observation)
                last_result = result
                history.append(self._history_item(step, decision, result))
                logger.event(
                    "tool_result",
                    summary=result.summary,
                    step=step,
                    result=result.model_dump(),
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
            return RunOutcome(False, summary, logger.run_id, str(logger.run_dir), limit)
        except KeyboardInterrupt:
            logger.event("run_interrupted", summary="Stopped by Ctrl+C.")
            logger.update_manifest(status="interrupted")
            raise
        except Exception as exc:
            logger.event("run_crashed", summary=str(exc), error_type=type(exc).__name__)
            logger.update_manifest(status="crashed", summary=str(exc))
            raise
