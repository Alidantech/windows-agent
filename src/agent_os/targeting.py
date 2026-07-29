from __future__ import annotations

import re
from difflib import SequenceMatcher

from agent_os.models import WindowInfo

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

_BROWSER_WORDS = {"google", "chrome", "brave", "edge", "microsoft", "firefox", "browser"}


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


def title_tokens(value: str) -> set[str]:
    tokens = {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 1}
    return tokens - _BROWSER_WORDS


def window_match_score(query: str, window: WindowInfo) -> float:
    q = query.strip().lower()
    title = window.title.lower()
    process = (window.process_name or "").lower()
    if not q:
        return 0.0
    if q == title:
        return 100.0
    if q in {process, process.removesuffix(".exe")}:
        return 96.0
    if q in title:
        return 90.0
    try:
        if re.search(query, window.title, re.IGNORECASE):
            return 93.0
    except re.error:
        pass
    q_tokens = title_tokens(query)
    t_tokens = title_tokens(window.title)
    overlap = len(q_tokens & t_tokens)
    if q_tokens and overlap:
        return 65.0 + 30.0 * overlap / len(q_tokens)
    return 60.0 * SequenceMatcher(None, q, title).ratio()


def best_window_match(
    query: str,
    windows: list[WindowInfo],
    minimum_score: float = 64.0,
) -> WindowInfo | None:
    ranked = sorted(
        ((window_match_score(query, window), window) for window in windows),
        key=lambda item: (item[0], item[1].active),
        reverse=True,
    )
    if not ranked or ranked[0][0] < minimum_score:
        return None
    return ranked[0][1]
