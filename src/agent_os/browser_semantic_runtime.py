from __future__ import annotations

from contextlib import suppress
from typing import Any

from agent_os.browser import BrowserElementRef
from agent_os.browser_semantic import (
    BrowserController as BaseBrowserController,
)
from agent_os.browser_semantic import (
    SemanticBrowserElementRef,
)


class BrowserController(BaseBrowserController):
    """Resolve only current visible semantic nodes after dynamic DOM rerenders."""

    def _locator(self, ref: BrowserElementRef) -> Any:
        if not isinstance(ref, SemanticBrowserElementRef):
            return super()._locator(ref)

        attempted: list[str] = []
        for label, locator in self._candidate_locators(ref):
            attempted.append(label)
            with suppress(Exception):
                visible = self._visible_matches(locator)
                if len(visible) == 1:
                    return visible[0]
                if len(visible) >= ref.occurrence:
                    return visible[ref.occurrence - 1]

        raise RuntimeError(
            f"Could not re-resolve a visible semantic element {ref.element_id} "
            f"({ref.role!r} {ref.name!r}). Tried: {', '.join(attempted) or 'none'}. "
            "A stale hidden node was not accepted; capture the current semantic page map."
        )


__all__ = ["BrowserController"]
