from __future__ import annotations

from agent_os.browser_semantic import SemanticBrowserElementRef
from agent_os.browser_semantic_runtime import BrowserController


class _FakeLocator:
    def __init__(self, labels: list[str], *, visible: bool = True) -> None:
        self.labels = labels
        self.visible = visible

    def count(self) -> int:
        return len(self.labels)

    def nth(self, index: int):
        return _FakeLocator([self.labels[index]], visible=self.visible)

    def is_visible(self) -> bool:
        return bool(self.labels) and self.visible


class _FakePage:
    def __init__(self) -> None:
        self.hidden_old_node = _FakeLocator(["old B0059"], visible=False)
        self.visible_new_node = _FakeLocator(["Live Performance"], visible=True)
        self.empty = _FakeLocator([])

    def is_closed(self) -> bool:
        return False

    def locator(self, selector: str):
        if "B0059" in selector:
            return self.hidden_old_node
        return self.empty

    def get_by_label(self, _name: str, exact: bool = True):
        return self.empty

    def get_by_role(self, role: str, name: str, exact: bool = True):
        if role == "option" and name == "Live Performance" and exact:
            return self.visible_new_node
        return self.empty

    def get_by_text(self, _name: str, exact: bool = True):
        return self.empty

    def get_by_placeholder(self, _name: str, exact: bool = True):
        return self.empty


def test_hidden_stale_selector_does_not_beat_visible_replacement() -> None:
    controller = BrowserController.__new__(BrowserController)
    controller._page = _FakePage()
    ref = SemanticBrowserElementRef(
        selector='[data-windows-agent-id="B0059"]',
        element_id="E0019",
        role="option",
        name="Live Performance",
    )

    resolved = controller._locator(ref)

    assert resolved.labels == ["Live Performance"]
    assert resolved.visible is True
