from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from agent_os.confirmation_policy import ConfirmationMode, ConfirmationPolicy
from agent_os.metrics import ActionMetric, RunMetrics
from agent_os.models import ExecutionResult
from agent_os.observation_contract import ObservationContractError, ObservationLedger
from agent_os.recovery import RecoveryBudget, RecoveryTracker
from agent_os.tools_controls import ToolExecutor as BaseToolExecutor


class ToolExecutor(BaseToolExecutor):
    """Consume one observation, execute one action, refresh, verify, and record evidence."""

    def __init__(self, *args, capture=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.capture = capture
        self.confirmations = ConfirmationPolicy()
        self.recovery = RecoveryTracker()
        self.metrics = RunMetrics()
        self.task = ""
        self._current_observation = None

    def configure_run(self, task: str) -> None:
        self.task = task
        self.recovery = RecoveryTracker(
            RecoveryBudget(
                max_repeated_strategy=getattr(
                    self.settings,
                    "max_repeated_strategy",
                    2,
                ),
                max_unknown_outcomes=getattr(
                    self.settings,
                    "max_unknown_outcomes",
                    1,
                ),
                max_locator_recoveries=getattr(
                    self.settings,
                    "max_locator_recoveries",
                    2,
                ),
                max_coordinate_fallbacks=getattr(
                    self.settings,
                    "max_coordinate_fallbacks",
                    3,
                ),
                max_consecutive_no_change=getattr(
                    self.settings,
                    "max_consecutive_no_change",
                    2,
                ),
            )
        )
        self.metrics.reset()

    @staticmethod
    def _element_label(decision, observation) -> str:
        if not decision.element_id:
            return ""
        element = next(
            (
                item
                for item in observation.uia.elements
                if item.element_id == decision.element_id
            ),
            None,
        )
        if element is None:
            return ""
        return " ".join(
            part
            for part in (
                element.name,
                element.placeholder or "",
                element.control_type,
            )
            if part
        )

    @staticmethod
    def _focused_editable(observation) -> tuple[bool, str | None]:
        for element in observation.uia.elements:
            if element.focused and element.enabled and not element.readonly:
                role = element.control_type.casefold()
                editable = bool(element.editable) or role in {
                    "edit",
                    "textbox",
                    "document",
                    "combobox",
                }
                if editable:
                    return True, element.element_id
        state = observation.state
        form_state = state.get("form_state")
        if isinstance(form_state, dict):
            active = form_state.get("activeElement")
            if isinstance(active, dict) and active.get("id"):
                return True, str(active.get("id"))
        return False, None

    def _physical_permission(self, observation, lease, reason: str):
        if reason == "fill_element fallback":
            return ExecutionResult(
                ok=False,
                summary=(
                    "The target does not expose a semantic text-value pattern. For safety, "
                    "Windows Agent will not click and type in one unverified action. Click the "
                    "field, capture fresh focus state, then use type_text."
                ),
                details={"focus_contract": "click-refresh-verify-focus-type"},
            )
        if reason == "typing":
            focused, element_id = self._focused_editable(observation)
            if not focused:
                return ExecutionResult(
                    ok=False,
                    summary=(
                        "Typing was blocked because the current observation does not prove that "
                        "an editable control has focus. Click a semantic field, re-observe, and type "
                        "only after focus is confirmed."
                    ),
                    details={"focus_contract": "required", "focused_element_id": element_id},
                )
        return super()._physical_permission(observation, lease, reason)

    def _validate_target(self, observation, lease) -> ExecutionResult | None:
        if lease.backend == "desktop" and hasattr(self.windows, "validate_bound_window"):
            try:
                diagnostics = self.windows.validate_bound_window(lease)
                observation.state["bound_window_validation"] = diagnostics
            except Exception as exc:
                return ExecutionResult(
                    ok=False,
                    summary=f"Target validation blocked the action: {exc}",
                    details={"target_validation": "failed"},
                )
        return None

    def _refresh(self, lease):
        if self.capture is None:
            raise RuntimeError("Production action broker has no capture service.")
        self.capture.set_lease_generation(lease.generation)
        if lease.backend == "browser":
            return self.capture.capture_browser(
                self.browser,
                lease.monitor_index,
                screenshot_path=None,
                lease_id=lease.lease_id,
            )
        return self.capture.capture(
            lease.capture_spec,
            screenshot_path=None,
            lease_id=lease.lease_id,
        )

    @staticmethod
    def _changed(before, after, result: ExecutionResult) -> bool:
        if "changed" in result.details:
            return bool(result.details.get("changed"))
        if before.capture_token != after.capture_token:
            return True
        before_contract = ObservationLedger.context(before)
        after_contract = ObservationLedger.context(after)
        return before_contract.get("target_fingerprint") != after_contract.get(
            "target_fingerprint"
        )

    @staticmethod
    def _semantic(decision, result: ExecutionResult) -> bool:
        input_mode = str(result.details.get("input") or "")
        return bool(
            decision.element_id
            or "semantic" in input_mode
            or input_mode.startswith("uia:")
            or decision.action == "select_option"
        )

    def _record(
        self,
        *,
        decision,
        result: ExecutionResult,
        duration_ms: int,
        changed: bool | None,
        before_id: str | None,
        after_id: str | None,
        backend: str,
        artifact_dir: Path,
    ) -> None:
        input_mode = str(result.details.get("input") or "none")
        metric = ActionMetric(
            sequence=len(self.metrics.actions) + 1,
            action=decision.action,
            status=str(result.status),
            ok=result.ok,
            input_mode=input_mode,
            duration_ms=duration_ms,
            changed=changed,
            before_observation_id=before_id,
            after_observation_id=after_id,
            target_backend=backend,
            semantic=self._semantic(decision, result),
            coordinate=decision.action in {"click", "double_click", "right_click", "move"},
            summary=result.summary[:500],
        )
        self.metrics.record(metric)
        self.metrics.write(artifact_dir, self.recovery.snapshot())

    def execute(self, decision, observation, lease, artifact_dir):
        started = time.monotonic()
        before_id = ObservationLedger.observation_id(observation)
        coordinate = decision.action in {"click", "double_click", "right_click", "move"}
        blocked_strategy = self.recovery.before_action(
            decision.signature(),
            coordinate=coordinate,
        )
        if blocked_strategy:
            return ExecutionResult(
                ok=False,
                summary=blocked_strategy,
                details={"recovery": self.recovery.snapshot()},
            )

        target_block = self._validate_target(observation, lease)
        if target_block is not None:
            return target_block

        assessment = self.confirmations.assess(
            decision,
            observation,
            task=self.task,
            guidance=(),
        )
        if assessment.mode in {ConfirmationMode.DENY, ConfirmationMode.HANDOFF}:
            return ExecutionResult(
                ok=False,
                summary=assessment.reason,
                details={
                    "risk_code": assessment.risk_code,
                    "confirmation_mode": assessment.mode.value,
                },
            )

        try:
            consumed_id = ObservationLedger.consume(
                observation,
                lease,
                action=decision.action,
                requested_observation_id=decision.observation_id,
            )
        except ObservationContractError as exc:
            return ExecutionResult(
                ok=False,
                summary=str(exc),
                details={"observation_contract": "rejected"},
            )

        if decision.action == "inspect_region":
            assert None not in {decision.x, decision.y, decision.x2, decision.y2}
            assert self.capture is not None
            self.capture.request_zoom(
                (
                    int(decision.x),
                    int(decision.y),
                    int(decision.x2),
                    int(decision.y2),
                )
            )
            result = ExecutionResult(
                ok=True,
                summary=(
                    "Queued a one-shot high-resolution inspection crop. The next observation "
                    "will show only that region; its crop coordinates are not valid for input."
                ),
                details={
                    "input": "inspection-only",
                    "before_observation_id": consumed_id,
                    "zoom_region_normalized": [
                        decision.x,
                        decision.y,
                        decision.x2,
                        decision.y2,
                    ],
                },
            )
            self._record(
                decision=decision,
                result=result,
                duration_ms=round((time.monotonic() - started) * 1000),
                changed=False,
                before_id=consumed_id,
                after_id=None,
                backend=observation.target.backend,
                artifact_dir=Path(artifact_dir),
            )
            return result

        if decision.action == "type_text":
            focused, element_id = self._focused_editable(observation)
            if not focused:
                result = ExecutionResult(
                    ok=False,
                    summary=(
                        "type_text was blocked because the current observation does not show a "
                        "focused editable control. Click or focus the intended field, then re-observe."
                    ),
                    details={
                        "before_observation_id": consumed_id,
                        "focus_contract": "failed",
                        "focused_element_id": element_id,
                    },
                )
                self._record(
                    decision=decision,
                    result=result,
                    duration_ms=round((time.monotonic() - started) * 1000),
                    changed=False,
                    before_id=consumed_id,
                    after_id=None,
                    backend=observation.target.backend,
                    artifact_dir=Path(artifact_dir),
                )
                return result

        self._current_observation = observation
        try:
            result = super().execute(decision, observation, lease, artifact_dir)
        finally:
            self._current_observation = None

        result.details.setdefault("before_observation_id", consumed_id)
        result.details.setdefault("expected_change", decision.expected_change)
        after = None
        changed: bool | None = None
        if result.ok:
            try:
                after = self._refresh(lease)
                changed = self._changed(observation, after, result)
                after_id = ObservationLedger.observation_id(after)
                result.details.update(
                    {
                        "after_observation_id": after_id,
                        "state_changed": changed,
                        "after_capture_token": after.capture_token,
                        "after_target": after.target.model_dump(),
                        "after_focus": (
                            after.state.get("accessibility_quality", {}).get(
                                "focused_element_id"
                            )
                            if isinstance(after.state.get("accessibility_quality"), dict)
                            else None
                        ),
                        "observation_rule": (
                            "The before observation is consumed. Plan the next action only from "
                            "a newly captured observation."
                        ),
                    }
                )
                result.status = "verified_success"
            except Exception as exc:
                result = ExecutionResult(
                    ok=False,
                    status="unknown_outcome",
                    summary=(
                        f"The {decision.action} input may have occurred, but the refreshed target "
                        f"could not be captured: {exc}. Do not repeat the action. Re-observe first."
                    ),
                    details={
                        **result.details,
                        "before_observation_id": consumed_id,
                        "refresh_error": str(exc),
                        "required_next_action": "observe",
                    },
                )
        else:
            result.status = "verified_failure"

        recovery_warning = self.recovery.after_action(
            status=str(result.status),
            changed=changed,
            locator_recovered=bool(result.details.get("locator_recovered")),
        )
        if recovery_warning:
            result.details["recovery_warning"] = recovery_warning
            result.details["recovery"] = self.recovery.snapshot()
            result.summary = f"{result.summary} Recovery rule: {recovery_warning}"

        after_id = (
            ObservationLedger.observation_id(after)
            if after is not None
            else str(result.details.get("after_observation_id") or "") or None
        )
        self._record(
            decision=decision,
            result=result,
            duration_ms=round((time.monotonic() - started) * 1000),
            changed=changed,
            before_id=consumed_id,
            after_id=after_id,
            backend=observation.target.backend,
            artifact_dir=Path(artifact_dir),
        )
        return result


__all__ = ["ToolExecutor"]
