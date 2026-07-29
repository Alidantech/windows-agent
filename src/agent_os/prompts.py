from __future__ import annotations

import json
from pathlib import Path

from agent_os.apps import AppLauncher
from agent_os.capture import CapturedObservation
from agent_os.lease import TargetLease
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
        lease: TargetLease,
        skills: list[Skill],
        history: list[dict[str, object]],
        last_result: ExecutionResult | None,
        user_guidance: list[str],
        controller_window: WindowInfo,
        controller_protected: bool,
        settings_summary: dict[str, object],
        session_context: list[dict[str, object]] | None = None,
    ) -> str:
        context = {
            "task": task,
            "step": step,
            "control_lease": lease.as_dict(),
            "settings": settings_summary,
            "capture_alignment": {
                "capture_token": observation.capture_token,
                "capture_source": observation.target.capture_source,
                "target": observation.target.model_dump(),
                "rule": "Every action must apply only to this exact leased target.",
            },
            "controller_window": {
                "hwnd": controller_window.hwnd,
                "title": controller_window.title,
                "process": controller_window.process_name,
                "protected": controller_protected,
            },
            "monitors": [item.model_dump() for item in observation.monitors],
            "visible_windows": [item.model_dump() for item in observation.windows],
            "ui_elements": [item.model_dump() for item in observation.uia.elements],
            "observation_state": observation.state,
            "available_app_aliases": self.app_launcher.available_aliases(),
            "recent_history": history[-10:],
            "last_execution_result": last_result.model_dump() if last_result else None,
            "user_guidance": user_guidance[-5:],
            "persistent_session_context": (session_context or [])[-12:],
        }
        return (
            "Select exactly one next action.\n\n"
            f"TASK CONTEXT (JSON):\n{json.dumps(context, indent=2, ensure_ascii=False)}\n\n"
            f"SELECTED SKILLS:\n{self._skills_text(skills)}\n\n"
            "The screenshot follows. Return only the typed action object."
        )

    def build_verifier_prompt(
        self,
        task: str,
        observation: CapturedObservation,
        lease: TargetLease,
        decision_reason: str,
        controller_window: WindowInfo,
        controller_protected: bool,
    ) -> str:
        context = {
            "task": task,
            "candidate_completion_reason": decision_reason,
            "control_lease": lease.as_dict(),
            "capture_token": observation.capture_token,
            "target": observation.target.model_dump(),
            "observation_state": observation.state,
            "controller_window": {
                "hwnd": controller_window.hwnd,
                "title": controller_window.title,
                "process": controller_window.process_name,
                "protected": controller_protected,
            },
            "ui_elements": [item.model_dump() for item in observation.uia.elements[:80]],
        }
        return (
            "Verify whether the exact task is visibly complete in the leased screenshot. "
            "An attempted action is not evidence of success.\n\n"
            f"CONTEXT:\n{json.dumps(context, indent=2, ensure_ascii=False)}"
        )
