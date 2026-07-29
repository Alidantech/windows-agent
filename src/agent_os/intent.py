from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

TaskKind = Literal["conversation", "desktop"]


@dataclass(frozen=True)
class TaskIntent:
    kind: TaskKind
    reason: str
    continue_browser: bool = False


class IntentRouter:
    """Route terminal conversation away from the expensive visual action loop."""

    _GREETING = re.compile(
        r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|howdy|yo)(?:\s+\w+){0,3}[!.?]*$",
        re.IGNORECASE,
    )
    _SOCIAL = re.compile(
        r"^(?:thanks|thank\s+you|okay|ok|great|nice|cool|bye|goodbye|see\s+you)(?:\s+\w+){0,4}[!.?]*$",
        re.IGNORECASE,
    )
    _QUESTION_START = re.compile(
        r"^(?:what|why|how|who|when|where|which|can|could|would|should|do|does|did|is|are|am|will|may)\b",
        re.IGNORECASE,
    )
    _URL = re.compile(
        r"(?:https?://|\b[a-z0-9][a-z0-9.-]*\.(?:com|co|org|net|io|ai|app|dev|site|xyz)(?:/\S*)?)",
        re.IGNORECASE,
    )
    _ACTION_CUES = re.compile(
        r"\b(?:open|launch|start|visit|browse|navigate|go\s+to|click|double\s+click|"
        r"right\s+click|type|enter|fill|select|choose|check|uncheck|scroll|drag|drop|"
        r"press|hotkey|create\s+(?:an?\s+)?account|sign\s*up|register|log\s*in|"
        r"login|sign\s*in|submit|send|post|upload|download|install|uninstall|delete|"
        r"rename|move|copy|test|smoke\s+test|inspect|capture|take\s+a\s+screenshot|"
        r"close|minimi[sz]e|maximi[sz]e)\b",
        re.IGNORECASE,
    )
    _COMPUTER_TARGET = re.compile(
        r"\b(?:browser|website|web\s*page|page|window|monitor|screen|desktop|"
        r"application|app|chrome|brave|edge|firefox|notepad|calculator|explorer|"
        r"vscode|terminal)\b",
        re.IGNORECASE,
    )
    _SCREEN_QUESTION = re.compile(
        r"\b(?:on|in|from)\s+(?:the\s+)?(?:screen|monitor|window|browser|page|desktop)\b|"
        r"\b(?:what|which)\s+(?:is|are)\s+(?:visible|open|shown)\b",
        re.IGNORECASE,
    )
    _CONTINUATION = re.compile(
        r"^(?:continue|proceed|next|go\s+on|carry\s+on|finish|complete|"
        r"create\s+(?:an?\s+)?account|sign\s*up|register|log\s*in|login|sign\s*in|"
        r"fill|submit|click|select|choose|enter|verify|use\s+the\s+site)\b",
        re.IGNORECASE,
    )

    def route(
        self,
        text: str,
        *,
        browser_active: bool = False,
        app_aliases: tuple[str, ...] = (),
    ) -> TaskIntent:
        normalized = " ".join(text.strip().split())
        lowered = normalized.lower()
        if not normalized:
            return TaskIntent("conversation", "empty input")
        if self._GREETING.fullmatch(normalized) or self._SOCIAL.fullmatch(normalized):
            return TaskIntent("conversation", "greeting or social acknowledgement")
        if self._SCREEN_QUESTION.search(normalized):
            return TaskIntent(
                "desktop",
                "question requires observing the assigned computer target",
            )
        if browser_active and self._CONTINUATION.search(normalized):
            return TaskIntent(
                "desktop",
                "continuation refers to the persistent browser session",
                True,
            )

        aliases = tuple(alias.lower() for alias in app_aliases if alias)
        alias_mentioned = any(
            re.search(rf"\b{re.escape(alias)}\b", lowered) for alias in aliases
        )
        has_action = bool(self._ACTION_CUES.search(normalized))
        has_target = bool(
            self._URL.search(normalized)
            or self._COMPUTER_TARGET.search(normalized)
            or alias_mentioned
        )
        is_question = normalized.endswith("?") or bool(
            self._QUESTION_START.search(normalized)
        )

        if is_question:
            if has_action and has_target:
                return TaskIntent(
                    "desktop",
                    "question explicitly requests a computer action",
                )
            return TaskIntent(
                "conversation",
                "general question does not require computer control",
            )
        if has_action or self._URL.search(normalized):
            return TaskIntent(
                "desktop",
                "explicit computer, application, browser, or website action",
                browser_active and bool(self._CONTINUATION.search(normalized)),
            )
        return TaskIntent("conversation", "no explicit computer action was requested")
