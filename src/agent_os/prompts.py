from __future__ import annotations

import json
from pathlib import Path

from agent_os.apps import AppLauncher
from agent_os.capture import CapturedObservation
from agent_os.lease import TargetLease
from agent_os.models import ExecutionResult, WindowInfo
from agent_os.skills import Skill
from agent_os.task_contract import TaskContract


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

    def build_chat_prompt(
        self,
        message: str,
        session_context: list[dict[str, object]] | None = None,
    ) -> str:
        context = {
            "user_message": message,
            "recent_session_context": (session_context or [])[-12:],
            "mode": "terminal_conversation",
            "computer_action_performed": False,
        }
        return (
            "Respond directly to the user inside the Windows Agent terminal. "
            "Do not select or describe operating-system actions.\n\n"
            f"CONVERSATION CONTEXT (JSON):\n{json.dumps(context, indent=2, ensure_ascii=False)}"
        )

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
        contract = TaskContract.from_task(task)
        context = {
            "task": task,
            "task_contract": {
                "requested_url": contract.requested_url,
                "navigation_only": contract.navigation_only,
                "immutable_scope": contract.scope_summary,
                "rule": (
                    "Never infer an adjacent workflow. When the exact requested end state is "
                    "visible, return done immediately."
                ),
            },
            "step": step,
            "control_lease": lease.as_dict(),
            "settings": settings_summary,
            "capture_alignment": {
                "capture_token": observation.capture_token,
                "capture_source": observation.target.capture_source,
                "target": observation.target.model_dump(),
                "rule": "Every action must apply only to this exact leased target.",
            },
            "visual_grounding": {
                "mode": observation.state.get("visual_grounding", "none"),
                "grounding_image": observation.state.get("grounding_image"),
                "marks": observation.state.get("grounding_marks", 0),
                "coordinate_space": observation.state.get("coordinate_space"),
                "rule": (
                    "Colored boxes and labels in the model image correspond exactly to "
                    "ui_elements.element_id. Prefer element IDs over coordinate clicks."
                ),
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
            "user_guidance": user_guidance[-8:],
            "persistent_session_context": (session_context or [])[-12:],
        }
        return (
            "Select exactly one next action for this actionable computer task. "
            "Do not continue merely because another control looks useful.\n\n"
            f"TASK CONTEXT (JSON):\n{json.dumps(context, indent=2, ensure_ascii=False)}\n\n"
            f"SELECTED SKILLS:\n{self._skills_text(skills)}\n\n"
            "The grounded screenshot follows. Return only the typed action object."
        )

    def build_verifier_prompt(
        self,
        task: str,
        observation: CapturedObservation,
        lease: TargetLease,
        decision_reason: str,
        controller_window: WindowInfo,
        controller_protected: bool,
        last_result: ExecutionResult | None = None,
    ) -> str:
        contract = TaskContract.from_task(task)
        context = {
            "task": task,
            "task_contract": {
                "requested_url": contract.requested_url,
                "navigation_only": contract.navigation_only,
                "immutable_scope": contract.scope_summary,
            },
            "candidate_completion_reason": decision_reason,
            "control_lease": lease.as_dict(),
            "capture_token": observation.capture_token,
            "target": observation.target.model_dump(),
            "observation_state": observation.state,
            "last_execution_result": last_result.model_dump() if last_result else None,
            "controller_window": {
                "hwnd": controller_window.hwnd,
                "title": controller_window.title,
                "process": controller_window.process_name,
                "protected": controller_protected,
            },
            "ui_elements": [item.model_dump() for item in observation.uia.elements[:100]],
        }
        return (
            "Verify only the exact user request in this fresh leased observation. "
            "For a navigation-only request, a matching current URL or valid redirect is "
            "completion; clicking or filling an adjacent workflow is scope overrun. "
            "An attempted action is not evidence of success, but a visibly changed destination "
            "page or successful deterministic tool result is valid evidence.\n\n"
            f"CONTEXT:\n{json.dumps(context, indent=2, ensure_ascii=False)}"
        )
