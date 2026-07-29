from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ActionName = Literal[
    "click", "double_click", "right_click", "click_element", "fill_element",
    "move", "type_text", "press_key", "hotkey", "scroll", "launch_app",
    "open_url", "activate_window", "smoke_test_site", "wait", "ask_user",
    "done", "fail",
]


class AgentDecision(BaseModel):
    action: ActionName = Field(description="Exactly one supported action.")
    reason: str = Field(min_length=1, max_length=500)
    x: int | None = Field(default=None, ge=0, le=1000)
    y: int | None = Field(default=None, ge=0, le=1000)
    element_id: str | None = None
    text: str | None = Field(default=None, max_length=4000)
    key: str | None = Field(default=None, max_length=50)
    keys: list[str] | None = Field(default=None, max_length=8)
    amount: int | None = Field(default=None, ge=-20, le=20)
    app: str | None = Field(default=None, max_length=100)
    url: str | None = Field(default=None, max_length=2000)
    browser: str | None = Field(default=None, max_length=100)
    window: str | None = Field(default=None, max_length=200)
    seconds: float | None = Field(default=None, ge=0.2, le=10.0)
    message: str | None = Field(default=None, max_length=1000)
    max_links: int | None = Field(default=None, ge=1, le=250)

    @model_validator(mode="after")
    def validate_action_fields(self) -> "AgentDecision":
        if self.action in {"click", "double_click", "right_click", "move"} and (
            self.x is None or self.y is None
        ):
            raise ValueError(f"{self.action} requires x and y")
        if self.action in {"click_element", "fill_element"} and not self.element_id:
            raise ValueError(f"{self.action} requires element_id")
        if self.action in {"fill_element", "type_text"} and self.text is None:
            raise ValueError(f"{self.action} requires text")
        if self.action == "press_key" and not self.key:
            raise ValueError("press_key requires key")
        if self.action == "hotkey" and not self.keys:
            raise ValueError("hotkey requires keys")
        if self.action == "scroll" and self.amount is None:
            raise ValueError("scroll requires amount")
        if self.action == "launch_app" and not self.app:
            raise ValueError("launch_app requires app")
        if self.action == "open_url" and not self.url:
            raise ValueError("open_url requires url")
        if self.action == "activate_window" and not self.window:
            raise ValueError("activate_window requires window")
        if self.action == "ask_user" and not self.message:
            raise ValueError("ask_user requires message")
        return self

    def signature(self) -> str:
        return "|".join([
            self.action, str(self.x), str(self.y), str(self.element_id), str(self.text),
            str(self.key), ",".join(self.keys or []), str(self.amount), str(self.app),
            str(self.url), str(self.browser), str(self.window), str(self.max_links),
        ])


class TaskVerification(BaseModel):
    complete: bool
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = Field(min_length=1, max_length=1000)
    next_hint: str | None = Field(default=None, max_length=500)


class Rectangle(BaseModel):
    left: int
    top: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def contains(self, x: int | float, y: int | float) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def intersection_area(self, other: "Rectangle") -> int:
        width = max(0, min(self.right, other.right) - max(self.left, other.left))
        height = max(0, min(self.bottom, other.bottom) - max(self.top, other.top))
        return width * height


class TargetInfo(BaseModel):
    spec: str
    kind: Literal["desktop", "monitor", "window", "browser"]
    label: str
    rect: Rectangle
    monitor_index: int | None = None
    hwnd: int | None = None
    backend: Literal["desktop", "browser"] = "desktop"
    url: str | None = None
    identity: str | None = None
    capture_source: Literal["screen", "print-window", "screen-fallback", "playwright"] = "screen"
    lease_id: str | None = None


class MonitorInfo(BaseModel):
    index: int
    primary: bool = False
    rect: Rectangle


class WindowInfo(BaseModel):
    hwnd: int
    title: str
    process_id: int | None = None
    process_name: str | None = None
    rect: Rectangle
    active: bool = False
    monitor_index: int | None = None


class UIElement(BaseModel):
    element_id: str
    name: str
    control_type: str
    automation_id: str | None = None
    enabled: bool = True
    visible: bool = True
    rect: Rectangle
    center_x: int = Field(ge=0, le=1000)
    center_y: int = Field(ge=0, le=1000)
    source: Literal["uia", "browser"] = "uia"


class ExecutionResult(BaseModel):
    ok: bool
    summary: str
    details: dict[str, object] = Field(default_factory=dict)
    task_complete: bool = False
    completion_evidence: str | None = None
