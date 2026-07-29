from __future__ import annotations

import html
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent_os.browser import BrowserController as BaseBrowserController
from agent_os.cancellation import CancellationToken


class BrowserController(BaseBrowserController):
    """Compatibility browser with cancellation and a visible deterministic report."""

    def __init__(self, settings, cancellation: CancellationToken) -> None:
        self.cancellation = cancellation
        try:
            super().__init__(settings, cancellation)
        except TypeError:
            super().__init__(settings)

    def abort(self) -> None:
        self.cancellation.cancel("Browser operation cancelled.")
        base_abort = getattr(super(), "abort", None)
        if callable(base_abort):
            base_abort()
            return
        self.close(force=True)

    def close(self, force: bool = False) -> None:
        base_close = super().close
        try:
            base_close(force=force)
        except TypeError:
            base_close()

    @staticmethod
    def _safe_name(index: int, url: str) -> str:
        parsed = urlparse(url)
        name = "".join(ch if ch.isalnum() else "-" for ch in f"{parsed.netloc}{parsed.path}")
        return f"{index:03d}-{name.strip('-')[:80] or 'page'}"

    def _show_report(self, report: dict[str, object]) -> None:
        rows = []
        for item in report.get("results", []):
            if not isinstance(item, dict):
                continue
            ok = bool(item.get("passed"))
            rows.append(
                "<tr><td>{}</td><td class='{}'>{}</td><td>{}</td><td>{}</td></tr>".format(
                    html.escape(str(item.get("requested_url", ""))),
                    "ok" if ok else "bad",
                    "PASS" if ok else "FAIL",
                    html.escape(str(item.get("status", "—"))),
                    html.escape(str(item.get("title", ""))),
                )
            )
        document = f"""<!doctype html><meta charset='utf-8'><title>Windows Agent smoke report</title>
<style>body{{font:15px Segoe UI;background:#101318;color:#eaf2f7;padding:28px}}h1{{color:#00e5ff}}.ok{{color:#39ff14}}.bad{{color:#ff4567}}table{{width:100%;border-collapse:collapse}}td,th{{padding:9px;border-bottom:1px solid #303842;text-align:left}}code{{color:#ffd166}}</style>
<h1>Windows Agent smoke report</h1><p><b>{report.get('passed', 0)} passed</b> · <b>{report.get('failed', 0)} failed</b> · {report.get('duplicates_skipped', 0)} duplicates skipped</p>
<p>Report: <code>{html.escape(str(report.get('report_path', '')))}</code></p><table><tr><th>URL</th><th>Result</th><th>HTTP</th><th>Title</th></tr>{''.join(rows)}</table>"""
        try:
            self.page.set_content(document, wait_until="domcontentloaded")
            self.page.bring_to_front()
        except Exception:
            pass

    def smoke_test_site(self, output_dir: Path, max_links: int) -> dict[str, object]:
        output_dir.mkdir(parents=True, exist_ok=True)
        inventory = self.discover_link_inventory(same_origin_only=True)
        all_links = list(inventory.get("links") or [])
        links = all_links[:max_links]
        results: list[dict[str, object]] = []
        for index, link in enumerate(links, start=1):
            self.cancellation.raise_if_cancelled()
            url = str(link["url"])
            page = self._context.new_page()
            page_errors: list[str] = []
            failures: list[str] = []
            page.on("pageerror", lambda error, bucket=page_errors: bucket.append(str(error)[:1000]))
            page.on("requestfailed", lambda request, bucket=failures: bucket.append(f"{request.method} {request.url}: {request.failure or 'failed'}"[:1200]))
            status = None
            error = None
            started = time.monotonic()
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=self.settings.browser_timeout_ms)
                status = response.status if response is not None else None
                page.wait_for_timeout(self.settings.browser_smoke_visual_delay_ms)
            except Exception as exc:
                error = str(exc)[:1200]
            title = ""
            try:
                title = page.title()
            except Exception:
                pass
            visible_error = None
            try:
                text = page.locator("body").inner_text(timeout=3000).lower()[:12000]
                visible_error = next((marker for marker in (
                    "internal server error", "application error", "page not found",
                    "404 not found", "something went wrong", "this site can’t be reached",
                    "this site can't be reached",
                ) if marker in text), None)
            except Exception:
                pass
            passed = error is None and (status is None or status < 400) and not page_errors and visible_error is None
            screenshot = output_dir / (self._safe_name(index, url) + ".png")
            try:
                page.screenshot(path=str(screenshot), full_page=False, animations="disabled")
            except Exception:
                screenshot = Path("")
            results.append({
                "index": index, "text": link.get("text", ""), "requested_url": url,
                "final_url": page.url, "status": status, "title": title, "passed": passed,
                "error": error, "visible_error": visible_error, "page_errors": page_errors,
                "request_failures": failures, "duration_ms": round((time.monotonic() - started) * 1000),
                "screenshot": str(screenshot) if str(screenshot) else None,
            })
            page.close()
        passed_count = sum(1 for item in results if item["passed"])
        report: dict[str, object] = {
            "start_url": self.page.url, "eligible_anchors": int(inventory.get("eligibleAnchors") or 0),
            "unique_links": len(all_links), "duplicates_skipped": int(inventory.get("duplicateUrls") or 0),
            "limited_by_max_links": len(all_links) > max_links, "max_links": max_links,
            "discovered_links": len(all_links), "tested_links": len(results), "passed": passed_count,
            "failed": len(results) - passed_count, "results": results,
        }
        report_path = output_dir / "smoke-report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(report_path)
        self._show_report(report)
        return report
