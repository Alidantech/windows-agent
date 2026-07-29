from __future__ import annotations

from agent_os.local_values import LOCAL_VALUE_TOKEN, local_value_vault
from agent_os.models import ExecutionResult
from agent_os.tools import ToolExecutor as BaseToolExecutor


class ToolExecutor(BaseToolExecutor):
    """Promote deterministic evidence and resolve local form values."""

    def __init__(self, *args, cancellation=None, **kwargs) -> None:
        self.cancellation = cancellation
        try:
            super().__init__(*args, cancellation=cancellation, **kwargs)
        except TypeError:
            super().__init__(*args, **kwargs)

    def execute(self, decision, observation, lease, artifact_dir):
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
                    element.control_type,
                    element.automation_id or "",
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
        return super().execute(decision, observation, lease, artifact_dir)

    def _browser_execute(self, decision, observation, lease, artifact_dir):
        if decision.action != "smoke_test_site":
            return super()._browser_execute(decision, observation, lease, artifact_dir)
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
