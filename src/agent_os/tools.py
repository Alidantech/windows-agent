from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.prompt import Confirm

from agent_os.apps import AppLauncher
from agent_os.browser import BrowserController, BrowserElementRef
from agent_os.capture import CapturedObservation
from agent_os.config import Settings
from agent_os.conflicts import UserActivityGuard
from agent_os.lease import TargetLease
from agent_os.models import AgentDecision, ExecutionResult
from agent_os.overlay import Overlay
from agent_os.safety import SafetyPolicy
from agent_os.windows import WindowManager

console = Console()


class ToolExecutor:
    def __init__(
        self,
        settings: Settings,
        app_launcher: AppLauncher,
        windows: WindowManager,
        browser: BrowserController,
        overlay: Overlay,
        dry_run: bool = False,
        auto_confirm: bool = False,
    ) -> None:
        self.settings = settings
        self.app_launcher = app_launcher
        self.windows = windows
        self.browser = browser
        self.overlay = overlay
        self.dry_run = dry_run
        self.auto_confirm = auto_confirm
        self.safety = SafetyPolicy(settings.confirm_risky)
        self.activity = UserActivityGuard()
        self.controller_hwnd: int | None = None
        self.allow_controller_interaction = False
        self._physical_approved = settings.physical_input_policy == "allow"

        import pyautogui

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.12
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
        return (
            rect.left + round(x * max(1, rect.width - 1) / 1000),
            rect.top + round(y * max(1, rect.height - 1) / 1000),
        )

    def _overlay_point(
        self,
        observation: CapturedObservation,
        lease: TargetLease,
        x: int,
        y: int,
        action: str,
    ) -> None:
        if observation.target.backend == "browser" and self.browser.active:
            sx, sy = self.browser.screen_point(x, y)
            self.overlay.cursor(sx, sy, action)
            return
        rect = lease.monitor_rect
        if rect is None:
            if observation.target.backend == "desktop":
                sx, sy = self._screen_point(observation, x, y)
                self.overlay.cursor(sx, sy, action)
            return
        sx = rect.left + round(x * max(1, rect.width - 1) / 1000)
        sy = rect.top + round(y * max(1, rect.height - 1) / 1000)
        self.overlay.cursor(sx, sy, action)

    def _confirm_if_needed(self, decision: AgentDecision) -> ExecutionResult | None:
        assessment = self.safety.assess(decision)
        if not assessment.allowed:
            return ExecutionResult(ok=False, summary=assessment.reason)
        if assessment.requires_confirmation and not self.auto_confirm:
            if not Confirm.ask(f"[yellow]{assessment.reason} Continue?[/yellow]", default=False):
                return ExecutionResult(ok=False, summary="User rejected the risky action.")
        return None

    def _validate_desktop_observation(
        self,
        observation: CapturedObservation,
        lease: TargetLease,
    ) -> ExecutionResult | None:
        if lease.backend != "desktop":
            return ExecutionResult(ok=False, summary="Desktop action requested for a browser lease.")
        if lease.bound_hwnd is not None and observation.target.hwnd != lease.bound_hwnd:
            return ExecutionResult(
                ok=False,
                summary=(
                    "Screenshot/control mismatch blocked: observation HWND "
                    f"{observation.target.hwnd} does not equal leased HWND {lease.bound_hwnd}."
                ),
            )
        if lease.monitor_rect is not None:
            if observation.target.rect.intersection_area(lease.monitor_rect) <= 0:
                return ExecutionResult(
                    ok=False,
                    summary="Controlled target escaped the assigned monitor; input was blocked.",
                )
        return None

    def _protect_controller(
        self,
        decision: AgentDecision,
        observation: CapturedObservation,
    ) -> ExecutionResult | None:
        if self.allow_controller_interaction or self.controller_hwnd is None:
            return None
        if observation.target.hwnd != self.controller_hwnd:
            return None
        if decision.action in {"activate_window", "launch_app", "open_url", "wait"}:
            return None
        return ExecutionResult(
            ok=False,
            summary="Protected the Agent OS controller from self-interaction. No input was sent.",
        )

    def _physical_permission(
        self,
        observation: CapturedObservation,
        lease: TargetLease,
        reason: str,
    ) -> ExecutionResult | None:
        policy = self.settings.physical_input_policy
        if policy == "deny":
            return ExecutionResult(
                ok=False,
                summary=(
                    f"Physical input is disabled ({reason}). Use isolated browser control or a UIA "
                    "semantic element."
                ),
            )
        if policy == "ask" and not self._physical_approved:
            if not Confirm.ask(
                f"[yellow]Agent needs the shared Windows mouse/keyboard for: {reason}. "
                "Allow physical fallback for this run?[/yellow]",
                default=False,
            ):
                return ExecutionResult(ok=False, summary="User denied shared physical input.")
            self._physical_approved = True

        if self.settings.cursor_activity_guard:
            activity = self.activity.sample()
            if activity.moving:
                return ExecutionResult(
                    ok=False,
                    summary="User cursor activity detected; physical fallback paused to avoid conflict.",
                    details={
                        "cursor_start": activity.start,
                        "cursor_end": activity.end,
                        "distance": activity.distance,
                    },
                )

        hwnd = observation.target.hwnd
        if hwnd is not None and self.windows.active_hwnd() != hwnd:
            if self.settings.conflict_policy == "cooperative":
                return ExecutionResult(
                    ok=False,
                    summary=(
                        "Another window owns foreground focus. Cooperative mode refused to steal focus "
                        "for physical input."
                    ),
                    details={"active_hwnd": self.windows.active_hwnd(), "target_hwnd": hwnd},
                )
            try:
                self.windows.activate_hwnd(hwnd)
                time.sleep(0.2)
            except Exception as exc:
                return ExecutionResult(ok=False, summary=f"Could not focus leased window: {exc}")
        return None

    @staticmethod
    def _element(
        observation: CapturedObservation,
        element_id: str,
    ) -> tuple[Any | None, Any | None]:
        wrapper = observation.uia.wrappers.get(element_id)
        element = next(
            (item for item in observation.uia.elements if item.element_id == element_id),
            None,
        )
        return wrapper, element

    def _browser_execute(
        self,
        decision: AgentDecision,
        observation: CapturedObservation,
        lease: TargetLease,
        artifact_dir: Path,
    ) -> ExecutionResult:
        action = decision.action
        if action in {"click", "double_click", "right_click", "move"}:
            assert decision.x is not None and decision.y is not None
            self._overlay_point(observation, lease, decision.x, decision.y, action)
            if action == "move":
                summary = self.browser.move_point(decision.x, decision.y)
            else:
                summary = self.browser.click_point(
                    decision.x,
                    decision.y,
                    click_count=2 if action == "double_click" else 1,
                    button="right" if action == "right_click" else "left",
                )
            return ExecutionResult(ok=True, summary=summary, details={"input": "browser-virtual"})

        if action in {"click_element", "fill_element"}:
            assert decision.element_id is not None
            wrapper, element = self._element(observation, decision.element_id)
            if not isinstance(wrapper, BrowserElementRef) or element is None:
                raise RuntimeError(f"Browser element {decision.element_id} is stale or unavailable.")
            self._overlay_point(observation, lease, element.center_x, element.center_y, action)
            if action == "click_element":
                summary = self.browser.click_element(wrapper)
            else:
                assert decision.text is not None
                summary = self.browser.fill_element(wrapper, decision.text)
            return ExecutionResult(ok=True, summary=summary, details={"input": "browser-virtual"})

        if action == "type_text":
            assert decision.text is not None
            return ExecutionResult(
                ok=True,
                summary=self.browser.type_text(decision.text),
                details={"input": "browser-virtual"},
            )
        if action == "press_key":
            assert decision.key is not None
            return ExecutionResult(
                ok=True,
                summary=self.browser.press_key(decision.key),
                details={"input": "browser-virtual"},
            )
        if action == "hotkey":
            return ExecutionResult(
                ok=True,
                summary=self.browser.hotkey(decision.keys or []),
                details={"input": "browser-virtual"},
            )
        if action == "scroll":
            assert decision.amount is not None
            return ExecutionResult(
                ok=True,
                summary=self.browser.scroll(decision.amount),
                details={"input": "browser-virtual"},
            )
        if action == "open_url":
            assert decision.url is not None
            summary = self.browser.open_url(decision.url, lease.monitor_rect, decision.browser)
            lease.bind_browser(self.browser.diagnostics().get("title") or "Isolated browser")
            return ExecutionResult(
                ok=True,
                summary=summary,
                details={"input": "browser-virtual", **self.browser.diagnostics()},
            )
        if action == "smoke_test_site":
            if decision.url:
                self.browser.open_url(decision.url, lease.monitor_rect, decision.browser)
                lease.bind_browser(self.browser.diagnostics().get("title") or "Isolated browser")
            report = self.browser.smoke_test_site(
                artifact_dir / "browser-smoke",
                decision.max_links or self.settings.browser_smoke_max_links,
            )
            return ExecutionResult(
                ok=True,
                summary=(
                    f"Smoke-tested {report['tested_links']} unique links: "
                    f"{report['passed']} passed, {report['failed']} failed; "
                    f"{report['duplicates_skipped']} duplicates skipped"
                    + ("; link limit reached" if report['limited_by_max_links'] else "")
                    + f". Report: {report['report_path']}"
                ),
                details={"input": "browser-virtual", "smoke_report": report},
            )
        if action == "wait":
            return ExecutionResult(
                ok=True,
                summary=self.browser.wait(decision.seconds or 1.0),
            )
        if action == "activate_window":
            try:
                self.browser.page.bring_to_front()
            except Exception:
                pass
            return ExecutionResult(ok=True, summary="Brought isolated browser to front.")
        raise RuntimeError(f"Action {action!r} is unavailable in browser mode.")

    def _physical_pointer(
        self,
        x: int,
        y: int,
        action: str,
    ) -> None:
        original = self.gui.position()
        self.overlay.cursor(x, y, action)
        try:
            self.gui.moveTo(x, y, duration=0.25)
            if action == "click":
                self.gui.click()
            elif action == "double_click":
                self.gui.doubleClick(interval=0.12)
            elif action == "right_click":
                self.gui.rightClick()
        finally:
            if self.settings.restore_user_cursor and action != "move":
                try:
                    self.gui.moveTo(original.x, original.y, duration=0.12)
                except Exception:
                    pass

    def execute(
        self,
        decision: AgentDecision,
        observation: CapturedObservation,
        lease: TargetLease,
        artifact_dir: Path,
    ) -> ExecutionResult:
        blocked = self._confirm_if_needed(decision)
        if blocked:
            return blocked
        if self.dry_run:
            return ExecutionResult(
                ok=True,
                summary=f"Dry run: would execute {decision.action}",
                details=decision.model_dump(exclude_none=True),
            )

        try:
            self.overlay.status(f"{decision.action}: {decision.reason[:90]}", "working")
            use_isolated_browser = (
                decision.action in {"open_url", "smoke_test_site"}
                and (
                    self.settings.control_mode == "browser"
                    or (
                        self.settings.control_mode == "auto"
                        and self.settings.browser_backend == "isolated"
                    )
                )
            )
            if use_isolated_browser:
                if decision.action == "open_url":
                    assert decision.url is not None
                    summary = self.browser.open_url(decision.url, lease.monitor_rect, decision.browser)
                    lease.bind_browser(self.browser.diagnostics().get("title") or "Isolated browser")
                    return ExecutionResult(
                        ok=True,
                        summary=summary,
                        details={"backend": "browser", **self.browser.diagnostics()},
                    )
                if decision.url:
                    self.browser.open_url(decision.url, lease.monitor_rect, decision.browser)
                lease.bind_browser(self.browser.diagnostics().get("title") or "Isolated browser")
                return self._browser_execute(decision, observation, lease, artifact_dir)

            if lease.backend == "browser" or observation.target.backend == "browser":
                return self._browser_execute(decision, observation, lease, artifact_dir)

            stale = self._validate_desktop_observation(observation, lease)
            if stale:
                return stale
            protected = self._protect_controller(decision, observation)
            if protected:
                return protected

            action = decision.action
            if action in {"click", "double_click", "right_click", "move"}:
                assert decision.x is not None and decision.y is not None
                permission = self._physical_permission(observation, lease, f"{action} by coordinates")
                if permission:
                    return permission
                x, y = self._screen_point(observation, decision.x, decision.y)
                if lease.monitor_rect and not lease.monitor_rect.contains(x, y):
                    raise RuntimeError("Coordinate lies outside the assigned monitor.")
                self._physical_pointer(x, y, action)
                return ExecutionResult(
                    ok=True,
                    summary=f"Executed {action} at ({x}, {y}) with shared physical pointer.",
                    details={"input": "physical", "screen_x": x, "screen_y": y},
                )

            if action in {"click_element", "fill_element"}:
                assert decision.element_id is not None
                wrapper, element = self._element(observation, decision.element_id)
                if wrapper is None or element is None:
                    raise RuntimeError(f"UI element {decision.element_id} is stale or unavailable.")
                if action == "click_element":
                    backend = self.windows.semantic_invoke(wrapper)
                    if backend:
                        self._overlay_point(
                            observation,
                            lease,
                            element.center_x,
                            element.center_y,
                            "semantic-click",
                        )
                        return ExecutionResult(
                            ok=True,
                            summary=f"Invoked {decision.element_id} through UI Automation.",
                            details={"input": f"uia:{backend}"},
                        )
                else:
                    assert decision.text is not None
                    backend = self.windows.semantic_set_text(wrapper, decision.text)
                    if backend:
                        return ExecutionResult(
                            ok=True,
                            summary=f"Filled {decision.element_id} through UI Automation.",
                            details={"input": f"uia:{backend}"},
                        )
                permission = self._physical_permission(observation, lease, f"{action} fallback")
                if permission:
                    return permission
                x, y = self._screen_point(observation, element.center_x, element.center_y)
                self._physical_pointer(x, y, "click")
                if action == "fill_element":
                    assert decision.text is not None
                    self.gui.hotkey("ctrl", "a")
                    self.gui.write(decision.text, interval=0.02)
                return ExecutionResult(
                    ok=True,
                    summary=f"Executed {action} using physical fallback.",
                    details={"input": "physical"},
                )

            if action == "type_text":
                assert decision.text is not None
                focused = self.windows.focused_wrapper(observation.uia)
                if focused:
                    element_id, wrapper = focused
                    backend = self.windows.semantic_set_text(wrapper, decision.text)
                    if backend:
                        return ExecutionResult(
                            ok=True,
                            summary=f"Set text on focused element {element_id} through UI Automation.",
                            details={"input": f"uia:{backend}"},
                        )
                permission = self._physical_permission(observation, lease, "typing")
                if permission:
                    return permission
                import pyperclip

                previous = None
                try:
                    previous = pyperclip.paste()
                except Exception:
                    pass
                pyperclip.copy(decision.text)
                self.gui.hotkey("ctrl", "v")
                if previous is not None:
                    time.sleep(0.1)
                    pyperclip.copy(previous)
                return ExecutionResult(
                    ok=True,
                    summary=f"Typed {len(decision.text)} characters using shared keyboard fallback.",
                    details={"input": "physical-keyboard"},
                )

            if action == "press_key":
                assert decision.key is not None
                permission = self._physical_permission(observation, lease, "key press")
                if permission:
                    return permission
                key = self._normalize_key(decision.key)
                self.gui.press(key)
                return ExecutionResult(ok=True, summary=f"Pressed key {key}.", details={"input": "physical-keyboard"})

            if action == "hotkey":
                permission = self._physical_permission(observation, lease, "hotkey")
                if permission:
                    return permission
                keys = [self._normalize_key(key) for key in decision.keys or []]
                self.gui.hotkey(*keys)
                return ExecutionResult(ok=True, summary=f"Pressed hotkey {'+'.join(keys)}.", details={"input": "physical-keyboard"})

            if action == "scroll":
                assert decision.amount is not None
                permission = self._physical_permission(observation, lease, "scroll")
                if permission:
                    return permission
                x = observation.target.rect.left + observation.target.rect.width // 2
                y = observation.target.rect.top + observation.target.rect.height // 2
                original = self.gui.position()
                self.overlay.cursor(x, y, "scroll")
                self.gui.moveTo(x, y, duration=0.2)
                self.gui.scroll(decision.amount)
                if self.settings.restore_user_cursor:
                    self.gui.moveTo(original.x, original.y, duration=0.12)
                return ExecutionResult(ok=True, summary=f"Scrolled {decision.amount} units.", details={"input": "physical"})

            if action == "launch_app":
                assert decision.app is not None
                return ExecutionResult(ok=True, summary=self.app_launcher.launch(decision.app), details={"backend": "process"})

            if action == "open_url":
                assert decision.url is not None
                return ExecutionResult(
                    ok=True,
                    summary=self.app_launcher.open_url(decision.url, decision.browser),
                    details={"backend": "system-browser"},
                )

            if action == "activate_window":
                assert decision.window is not None
                window = self.windows.activate(decision.window)
                return ExecutionResult(
                    ok=True,
                    summary=f"Activated window: {window.title}",
                    details={"hwnd": window.hwnd, "title": window.title},
                )

            if action == "smoke_test_site":
                raise RuntimeError("smoke_test_site requires the isolated browser backend.")

            if action == "wait":
                seconds = decision.seconds or 1.0
                time.sleep(seconds)
                return ExecutionResult(ok=True, summary=f"Waited {seconds:.1f} seconds.")

            raise RuntimeError(f"Action {action!r} is handled by the agent loop.")
        except Exception as exc:
            self.overlay.status(str(exc)[:100], "error")
            return ExecutionResult(ok=False, summary=f"{decision.action} failed: {exc}")
