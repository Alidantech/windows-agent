from __future__ import annotations

import re

CONTROLLER_TASK_TERMS = (
    "terminal",
    "console",
    "command prompt",
    "powershell",
    "git bash",
    "windows terminal",
    "cmd.exe",
    "wt.exe",
)


def task_allows_controller(task: str, target_spec: str, controller_title: str) -> bool:
    lowered_task = task.lower()
    lowered_target = target_spec.lower()
    if any(term in lowered_task for term in CONTROLLER_TASK_TERMS):
        return True
    if lowered_target.startswith("window:"):
        pattern = lowered_target.split(":", 1)[1]
        try:
            return re.search(pattern, controller_title, re.IGNORECASE) is not None
        except re.error:
            return pattern in controller_title.lower()
    return False
