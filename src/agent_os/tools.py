from __future__ import annotations

import time

from rich.console import Console
from rich.prompt import Confirm

from agent_os.apps import AppLauncher
from agent_os.capture import CapturedObservation
from agent_os.config import Settings
from agent_os.models import AgentDecision, ExecutionResult
from agent_os.safety import SafetyPolicy
from agent_os.windows import WindowManager

console = Console()


class ToolExecutor:
    def __init__(
        self,
        settings: Settings,
        app_launcher: AppLauncher,
        window_manager: WindowManager,
        dry_run: bool = False,
        auto_confirm: bool = False,
    ) -> None:
        self.settings = settings
        self.app_launcher = app_launcher
        self.windows = window_manager
        self.dry_run = dry_run
        self.auto_confirm = auto_confirm
        self.safety = SafetyPolicy(confirm_risky=settings.confirm_risky)
        self.controller_hwnd: int | None = None
        self.allow_controller_interaction = False

        import pyautogui

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.15
        self.gui = pyautogui

    def configure_controller(self, hwnd: int | None, allow_interaction: bool) -> None:
        self.controller_hwnd = hwnd
        self.allow_controller_interaction = allow_interaction

    @staticmethod
    def _normalize_key(key: str) -> str:
        aliases = {
            "win": "winleft",
            "windows": "winleft",
            "return": "enter",
            "escape": "esc",
            "control": "ctrl",
        }
        return aliases.get(key.strip().lower(), key.strip().lower())

    @staticmethod
    def _screen_point(observation: CapturedObservation, x: int, y: int) -> tuple[int, int]:
        rect = observation.target.rect
        screen_x = rect.left + round(x * max(1, rect.width - 1) / 1000)
        screen_y = rect.top + round(y * max(1, rect.height - 1) / 1000)
        return screen_x, screen_y

    def _confirm_if_needed(self, decision: AgentDecision) -> ExecutionResult | None:
        assessment = self.safety.assess(decision)
        if not assessment.allowed:
            return ExecutionResult(ok=False, summary=assessment.reason)
        if assessment.requires_confirmation and not self.auto_confirm:
            approved = Confirm.ask(f"[yellow]{assessment.reason} Continue?[/yellow]", default=False)
            if not approved:
                return ExecutionResult(ok=False, summary="User rejected the risky action.")
        return None

    def _focus_observation_target(
        self,
        decision: AgentDecision,
        observation: CapturedObservation,
    ) -> ExecutionResult | None:
        foreground_actions = {
            "click",
            "double_click",
            "right_click",
            "click_element",
            "move",
            "type_text",
            "press_key",
            "hotkey",
            "scroll",
        }
        hwnd = observation.target.hwnd
        if decision.action not in foreground_actions or hwnd is None:
            return None
        try:
            if self.windows.active_hwnd() != hwnd:
                window = self.windows.activate_hwnd(hwnd)
                time.sleep(0.3)
                return ExecutionResult(
                    ok=True,
                    summary=f"Focused captured target before input: {window.title}",
                    details={"focused_hwnd": hwnd},
                )
        except Exception as exc:
            return ExecutionResult(
                ok=False,
                summary=f"Could not focus the captured target before input: {exc}",
            )
        return None

    def _protect_controller(
        self,
        decision: AgentDecision,
        observation: CapturedObservation,
    ) -> ExecutionResult | None:
        if self.allow_controller_interaction or self.controller_hwnd is None:
            return None

        target_is_controller = observation.target.hwnd == self.controller_hwnd
        try:
            foreground_is_controller = self.windows.active_hwnd() == self.controller_hwnd
        except Exception:
            foreground_is_controller = target_is_controller

        if not (target_is_controller or foreground_is_controller):
            return None

        always_allowed = {"activate_window", "launch_app", "open_url", "wait"}
        if decision.action in always_allowed:
            return None

        if decision.action == "press_key" and self._normalize_key(decision.key or "") == "winleft":
            return None
        if decision.action == "hotkey":
            normalized = {self._normalize_key(key) for key in decision.keys or []}
            if normalized in ({"ctrl", "esc"}, {"alt", "tab"}):
                return None

        return ExecutionResult(
            ok=False,
            summary=(
                "Protected the Agent OS controller terminal from self-interaction. "
                "Activate the intended application window, launch it, or open the URL before typing/clicking."
            ),
            details={"controller_hwnd": self.controller_hwnd},
        )

    def execute(
        self,
        decision: AgentDecision,
        observation: CapturedObservation,
    ) -> ExecutionResult:
        blocked = self._confirm_if_needed(decision)
        if blocked:
            return blocked

        focus_result = self._focus_observation_target(decision, observation)
        if focus_result is not None and not focus_result.ok:
            return focus_result

        protected = self._protect_controller(decision, observation)
        if protected:
            return protected

        if self.dry_run:
            return ExecutionResult(
                ok=True,
                summary=f"Dry run: would execute {decision.action}",
                details=decision.model_dump(exclude_none=True),
            )

        try:
            action = decision.action
            if action in {"click", "double_click", "right_click", "move"}:
                assert decision.x is not None and decision.y is not None
                x, y = self._screen_point(observation, decision.x, decision.y)
                if action == "move":
                    self.gui.moveTo(x, y, duration=0.35)
                elif action == "double_click":
                    self.gui.moveTo(x, y, duration=0.25)
                    self.gui.doubleClick(interval=0.12)
                elif action == "right_click":
                    self.gui.moveTo(x, y, duration=0.25)
                    self.gui.rightClick()
                else:
                    self.gui.moveTo(x, y, duration=0.25)
                    self.gui.click()
                return ExecutionResult(
                    ok=True,
                    summary=f"Executed {action} at screen ({x}, {y}).",
                    details={"screen_x": x, "screen_y": y},
                )

            if action == "click_element":
                assert decision.element_id is not None
                wrapper = observation.uia.wrappers.get(decision.element_id)
                element = next(
                    (item for item in observation.uia.elements if item.element_id == decision.element_id),
                    None,
                )
                if wrapper is not None:
                    try:
                        wrapper.click_input()
                        return ExecutionResult(
                            ok=True,
                            summary=f"Clicked UI Automation element {decision.element_id}.",
                        )
                    except Exception:
                        pass
                if element is None:
                    raise RuntimeError(f"UI element {decision.element_id} is no longer available.")
                x, y = self._screen_point(observation, element.center_x, element.center_y)
                self.gui.moveTo(x, y, duration=0.25)
                self.gui.click()
                return ExecutionResult(
                    ok=True,
                    summary=f"Clicked element {decision.element_id} by its center point.",
                    details={"screen_x": x, "screen_y": y},
                )

            if action == "type_text":
                assert decision.text is not None
                if len(decision.text) > self.settings.max_typed_chars:
                    raise RuntimeError(
                        f"Text exceeds configured maximum of {self.settings.max_typed_chars} characters."
                    )
                import pyperclip

                previous: str | None
                try:
                    previous = pyperclip.paste()
                except Exception:
                    previous = None
                pyperclip.copy(decision.text)
                self.gui.hotkey("ctrl", "v")
                time.sleep(0.15)
                if previous is not None:
                    try:
                        pyperclip.copy(previous)
                    except Exception:
                        pass
                return ExecutionResult(
                    ok=True,
                    summary=f"Typed {len(decision.text)} characters using clipboard paste.",
                )

            if action == "press_key":
                assert decision.key is not None
                key = self._normalize_key(decision.key)
                self.gui.press(key)
                return ExecutionResult(ok=True, summary=f"Pressed key {key}.")

            if action == "hotkey":
                keys = [self._normalize_key(key) for key in decision.keys or []]
                self.gui.hotkey(*keys)
                return ExecutionResult(ok=True, summary=f"Pressed hotkey {'+'.join(keys)}.")

            if action == "scroll":
                assert decision.amount is not None
                self.gui.scroll(decision.amount)
                return ExecutionResult(ok=True, summary=f"Scrolled {decision.amount} units.")

            if action == "launch_app":
                assert decision.app is not None
                message = self.app_launcher.launch(decision.app)
                time.sleep(1.0)
                return ExecutionResult(ok=True, summary=message)

            if action == "open_url":
                assert decision.url is not None
                message = self.app_launcher.open_url(decision.url, decision.browser)
                time.sleep(1.5)
                return ExecutionResult(ok=True, summary=message)

            if action == "activate_window":
                assert decision.window is not None
                window = self.windows.activate(decision.window)
                time.sleep(0.4)
                return ExecutionResult(
                    ok=True,
                    summary=f"Activated window: {window.title}",
                    details={"hwnd": window.hwnd, "title": window.title},
                )

            if action == "wait":
                seconds = decision.seconds or 1.0
                time.sleep(seconds)
                return ExecutionResult(ok=True, summary=f"Waited {seconds:.1f} seconds.")

            raise RuntimeError(f"Action {action!r} is handled by the agent loop, not the executor.")
        except Exception as exc:
            return ExecutionResult(ok=False, summary=f"{decision.action} failed: {exc}")
