from __future__ import annotations

import json
from pathlib import Path

from agent_os.apps import AppLauncher
from agent_os.capture import CapturedObservation
from agent_os.models import ExecutionResult, WindowInfo
from agent_os.skills import Skill


class PromptBuilder:
    def __init__(self, prompts_dir: Path, app_launcher: AppLauncher) -> None:
        self.prompts_dir = prompts_dir
        self.app_launcher = app_launcher
        self.system_instruction = self._read("system.md")
        self.verifier_instruction = self._read("verifier.md")

    def _read(self, name: str) -> str:
        path = self.prompts_dir / name
        if not path.exists():
            raise RuntimeError(f"Required prompt file is missing: {path}")
        return path.read_text(encoding="utf-8").strip()

    @staticmethod
    def _skills_text(skills: list[Skill]) -> str:
        if not skills:
            return "No additional task skills selected."
        return "\n\n".join(f"## Skill: {skill.name}\n{skill.body}" for skill in skills)

    def build_step_prompt(
        self,
        task: str,
        step: int,
        observation: CapturedObservation,
        skills: list[Skill],
        history: list[dict[str, object]],
        last_result: ExecutionResult | None,
        user_guidance: list[str],
        requested_target: str | None = None,
        controller_window: WindowInfo | None = None,
        controller_protected: bool = False,
    ) -> str:
        target = observation.target
        windows = [
            {
                "title": item.title,
                "process": item.process_name,
                "active": item.active,
                "rect": item.rect.model_dump(),
            }
            for item in observation.windows
        ]
        elements = [item.model_dump() for item in observation.uia.elements]
        monitor_data = [item.model_dump() for item in observation.monitors]

        context = {
            "task": task,
            "step": step,
            "requested_target": requested_target or target.spec,
            "current_observation_target": target.model_dump(),
            "controller_window": (
                {
                    "hwnd": controller_window.hwnd,
                    "title": controller_window.title,
                    "process": controller_window.process_name,
                    "protected": controller_protected,
                }
                if controller_window
                else None
            ),
            "monitors": monitor_data,
            "visible_windows": windows,
            "ui_automation_elements": elements,
            "available_app_aliases": self.app_launcher.available_aliases(),
            "recent_history": history[-8:],
            "last_execution_result": last_result.model_dump() if last_result else None,
            "user_guidance": user_guidance[-5:],
        }

        return (
            "Select the next single action for this desktop task.\n\n"
            f"TASK CONTEXT (JSON):\n{json.dumps(context, indent=2, ensure_ascii=False)}\n\n"
            f"SELECTED SKILLS:\n{self._skills_text(skills)}\n\n"
            "The screenshot follows this text. Return only the typed action object."
        )

    def build_verifier_prompt(
        self,
        task: str,
        observation: CapturedObservation,
        decision_reason: str,
        requested_target: str | None = None,
        controller_window: WindowInfo | None = None,
        controller_protected: bool = False,
    ) -> str:
        context = {
            "task": task,
            "candidate_completion_reason": decision_reason,
            "requested_target": requested_target or observation.target.spec,
            "current_observation_target": observation.target.model_dump(),
            "controller_window": (
                {
                    "hwnd": controller_window.hwnd,
                    "title": controller_window.title,
                    "process": controller_window.process_name,
                    "protected": controller_protected,
                }
                if controller_window
                else None
            ),
            "ui_automation_elements": [item.model_dump() for item in observation.uia.elements[:60]],
        }
        return (
            "Verify whether the task is visibly complete in the attached screenshot. "
            "Do not assume an action succeeded merely because it was attempted.\n\n"
            f"CONTEXT:\n{json.dumps(context, indent=2, ensure_ascii=False)}"
        )
