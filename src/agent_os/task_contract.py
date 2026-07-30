from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from agent_os.models import AgentDecision

_URL = re.compile(
    r"(?P<url>https?://[^\s]+|\b[a-z0-9][a-z0-9.-]*\.(?:com|co|org|net|io|ai|app|dev|site|xyz)(?:/[^\s]*)?)",
    re.IGNORECASE,
)
_NAVIGATION = re.compile(r"\b(?:open|visit|browse|navigate|go\s+to|load|show)\b", re.IGNORECASE)
_EXTENDED_ACTION = re.compile(
    r"\b(?:click|fill|type|enter|select|choose|submit|create|register|sign\s*up|"
    r"log\s*in|login|test|smoke\s+test|download|upload|inspect|delete|purchase|buy|send|post)\b",
    re.IGNORECASE,
)
_BROWSER_APP = re.compile(r"\b(?:chrome|chromium|browser|edge|brave|firefox)\b", re.IGNORECASE)


def _normalize_url(value: str) -> str:
    text = value.strip().rstrip(".,;:!?)\"]}")
    if "://" not in text:
        text = f"https://{text}"
    return text


@dataclass(frozen=True)
class TaskContract:
    task: str
    requested_url: str | None = None
    navigation_only: bool = False

    @classmethod
    def from_task(cls, task: str) -> "TaskContract":
        normalized = " ".join(task.strip().split())
        match = _URL.search(normalized)
        requested_url = _normalize_url(match.group("url")) if match else None
        remainder = normalized
        if match:
            remainder = normalized[: match.start()] + " " + normalized[match.end() :]
        navigation_only = bool(
            requested_url
            and _NAVIGATION.search(normalized)
            and not _EXTENDED_ACTION.search(remainder)
        )
        return cls(task=normalized, requested_url=requested_url, navigation_only=navigation_only)

    @property
    def scope_summary(self) -> str:
        if self.navigation_only and self.requested_url:
            return (
                f"Open the requested URL {self.requested_url} and stop. Do not click, fill, "
                "scroll, or continue into another workflow after the page is loaded."
            )
        return "Perform only the explicit user request; never infer an adjacent workflow."

    def normalize_decision(self, decision: AgentDecision) -> tuple[AgentDecision, str | None]:
        if not (self.navigation_only and self.requested_url):
            return decision, None
        if decision.action == "launch_app" and _BROWSER_APP.search(decision.app or ""):
            return (
                AgentDecision(
                    action="open_url",
                    url=self.requested_url,
                    browser=decision.app,
                    reason="Use the isolated browser directly for the navigation-only request.",
                ),
                "Replaced browser launch with direct isolated-browser navigation.",
            )
        return decision, None

    def action_violation(self, decision: AgentDecision) -> str | None:
        if not self.navigation_only:
            return None
        allowed = {"open_url", "activate_window", "wait", "done", "fail"}
        if decision.action not in allowed:
            return (
                f"Action {decision.action!r} exceeds the navigation-only task. "
                "The agent must stop after the requested URL is open."
            )
        return None

    def url_matches(self, current_url: str | None) -> bool:
        if not self.requested_url or not current_url:
            return False
        requested = urlparse(_normalize_url(self.requested_url))
        current = urlparse(_normalize_url(current_url))
        if requested.hostname != current.hostname:
            return False
        requested_path = requested.path.rstrip("/")
        current_path = current.path.rstrip("/")
        if not requested_path:
            return True
        return current_path == requested_path or current_path.startswith(requested_path + "/")
