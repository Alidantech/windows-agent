from __future__ import annotations

from agent_os.browser import BrowserElementRef
from agent_os.local_values import LOCAL_VALUE_TOKEN, local_value_vault
from agent_os.models import ExecutionResult
from agent_os.tools import ToolExecutor as BaseToolExecutor


class ToolExecutor(BaseToolExecutor):
    """Resolve local form values and return verified browser interaction state."""

    def __init__(self, *args, cancellation=None, **kwargs) -> None:
        self.cancellation = cancellation
        try:
            super().__init__(*args, cancellation=cancellation, **kwargs)
        except TypeError:
            super().__init__(*args, **kwargs)

    def execute(self, decision, observation, lease, artifact_dir):
        local_value_used = False
        if (
            decision.action in {"fill_element", "type_text"}
            and decision.text == LOCAL_VALUE_TOKEN
        ):
            if decision.action != "fill_element" or not decision.element_id:
                return ExecutionResult(
                    ok=False,
                    summary=(
                        "A local form value requires an exact fill_element target. "
                        "Select the intended field instead of using free typing."
                    ),
                )
            element = next(
                (
                    item
                    for item in observation.uia.elements
                    if item.element_id == decision.element_id
                ),
                None,
            )
            if element is None:
                return ExecutionResult(
                    ok=False,
                    summary="The selected field is stale. Capture the page and select it again.",
                )
            target = " ".join(
                part
                for part in (
                    element.name,
                    element.placeholder or "",
                    element.control_type,
                )
                if part
            )
            if not local_value_vault.matches_target(target):
                return ExecutionResult(
                    ok=False,
                    summary=(
                        "The locally supplied value belongs to a different field. "
                        "Ask the user for the value required by this field."
                    ),
                )
            value = local_value_vault.get()
            if value is None:
                return ExecutionResult(
                    ok=False,
                    summary=(
                        "The local form value is no longer available. "
                        "Ask the user for it again."
                    ),
                )
            decision = decision.model_copy(
                update={
                    "text": value,
                    "reason": "Use the form value supplied locally by the user.",
                }
            )
            local_value_used = True
        try:
            return super().execute(decision, observation, lease, artifact_dir)
        finally:
            if local_value_used:
                local_value_vault.clear()

    @staticmethod
    def _invalid_summary(details: dict[str, object]) -> str:
        missing = [str(item) for item in details.get("missing_required") or []]
        invalid = []
        for item in details.get("invalid_fields") or []:
            if isinstance(item, dict):
                name = str(item.get("name") or "field")
                message = str(item.get("message") or "invalid")
                invalid.append(f"{name}: {message}")
            else:
                invalid.append(str(item))
        parts = []
        if missing:
            parts.append("missing required: " + ", ".join(dict.fromkeys(missing)))
        if invalid:
            parts.append("invalid: " + "; ".join(dict.fromkeys(invalid)))
        return " | ".join(parts)

    def _browser_execute(self, decision, observation, lease, artifact_dir):
        self.browser.set_pointer_sink(self.overlay.cursor)
        action = decision.action

        if action in {"click", "double_click", "right_click", "move"}:
            assert decision.x is not None and decision.y is not None
            if action == "move":
                summary = self.browser.move_point(decision.x, decision.y)
            else:
                summary = self.browser.click_point(
                    decision.x,
                    decision.y,
                    click_count=2 if action == "double_click" else 1,
                    button="right" if action == "right_click" else "left",
                )
            return ExecutionResult(
                ok=True,
                summary=summary,
                details={"input": "browser-virtual", "coordinates": "css-pixels"},
            )

        if action in {"click_element", "fill_element"}:
            assert decision.element_id is not None
            wrapper, element = self._element(observation, decision.element_id)
            if not isinstance(wrapper, BrowserElementRef) or element is None:
                raise RuntimeError(
                    f"Browser element {decision.element_id} is stale or unavailable."
                )
            if action == "click_element":
                if hasattr(self.browser, "click_element_state"):
                    summary, state = self.browser.click_element_state(wrapper, element)
                else:
                    summary = self.browser.click_element(wrapper)
                    state = {}
                invalid = self._invalid_summary(state)
                if element.is_submit and invalid:
                    return ExecutionResult(
                        ok=False,
                        summary=(
                            f"Submission did not advance because the form is incomplete: {invalid}. "
                            "Do not click the submit button again until these fields are resolved."
                        ),
                        details={
                            "input": "browser-virtual",
                            "element_id": decision.element_id,
                            "coordinates": "css-pixels",
                            **state,
                        },
                    )
                if element.is_submit and state and not bool(state.get("changed")):
                    alerts = "; ".join(str(item) for item in state.get("alerts") or [])
                    suffix = f" Visible messages: {alerts}" if alerts else ""
                    return ExecutionResult(
                        ok=False,
                        summary=(
                            "The submit/proceed click produced no observable page or form-state "
                            f"change. Do not repeat the click; inspect validation or ask the user.{suffix}"
                        ),
                        details={
                            "input": "browser-virtual",
                            "element_id": decision.element_id,
                            "coordinates": "css-pixels",
                            **state,
                        },
                    )
                return ExecutionResult(
                    ok=True,
                    summary=summary,
                    details={
                        "input": "browser-virtual",
                        "element_id": decision.element_id,
                        "coordinates": "css-pixels",
                        **state,
                    },
                )

            assert decision.text is not None
            if hasattr(self.browser, "fill_element_state"):
                summary, state = self.browser.fill_element_state(
                    wrapper,
                    element,
                    decision.text,
                )
            else:
                summary = self.browser.fill_element(wrapper, decision.text)
                state = {}
            if decision.text and state and not bool(state.get("has_value")):
                return ExecutionResult(
                    ok=False,
                    summary=(
                        f"The value did not remain in browser element {decision.element_id}. "
                        "The control may require a selection, date picker, or different input method."
                    ),
                    details={
                        "input": "browser-virtual",
                        "element_id": decision.element_id,
                        "coordinates": "css-pixels",
                        **state,
                    },
                )
            if state.get("valid") is False:
                message = str(state.get("validation_message") or "the value is invalid")
                return ExecutionResult(
                    ok=False,
                    summary=(
                        f"Filled browser element {decision.element_id}, but validation rejected it: "
                        f"{message}. Do not submit until the value is corrected."
                    ),
                    details={
                        "input": "browser-virtual",
                        "element_id": decision.element_id,
                        "coordinates": "css-pixels",
                        **state,
                    },
                )
            return ExecutionResult(
                ok=True,
                summary=summary,
                details={
                    "input": "browser-virtual",
                    "element_id": decision.element_id,
                    "coordinates": "css-pixels",
                    **state,
                },
            )

        if action == "smoke_test_site":
            if decision.url:
                self.browser.open_url(decision.url, lease.monitor_rect, decision.browser)
                lease.bind_browser(
                    self.browser.diagnostics().get("title") or "Isolated browser"
                )
            report = self.browser.smoke_test_site(
                artifact_dir / "browser-smoke",
                decision.max_links or self.settings.browser_smoke_max_links,
            )
            summary = (
                f"Smoke-tested {report['tested_links']} unique links: "
                f"{report['passed']} passed, {report['failed']} failed; "
                f"{report['duplicates_skipped']} duplicates skipped. "
                f"Report: {report['report_path']}"
            )
            return ExecutionResult(
                ok=True,
                summary=summary,
                details={"input": "browser-virtual", "smoke_report": report},
                task_complete=True,
                completion_evidence=str(report["report_path"]),
            )

        return super()._browser_execute(decision, observation, lease, artifact_dir)
