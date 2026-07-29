from __future__ import annotations

from agent_os.models import ExecutionResult
from agent_os.tools import ToolExecutor as BaseToolExecutor


class ToolExecutor(BaseToolExecutor):
    """Compatibility executor that promotes deterministic tool evidence."""

    def __init__(self, *args, cancellation=None, **kwargs) -> None:
        self.cancellation = cancellation
        try:
            super().__init__(*args, cancellation=cancellation, **kwargs)
        except TypeError:
            super().__init__(*args, **kwargs)

    def _browser_execute(self, decision, observation, lease, artifact_dir):
        if decision.action != "smoke_test_site":
            return super()._browser_execute(decision, observation, lease, artifact_dir)
        if decision.url:
            self.browser.open_url(decision.url, lease.monitor_rect, decision.browser)
            lease.bind_browser(self.browser.diagnostics().get("title") or "Isolated browser")
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
