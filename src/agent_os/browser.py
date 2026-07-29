from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image

from agent_os.config import Settings
from agent_os.models import Rectangle, UIElement
from agent_os.windows import UIASnapshot


@dataclass(frozen=True)
class BrowserElementRef:
    selector: str
    element_id: str


@dataclass
class BrowserSnapshot:
    title: str
    url: str
    image: Image.Image
    image_bytes: bytes
    uia: UIASnapshot
    viewport: Rectangle
    browser_name: str


class BrowserController:
    """Visible Playwright browser with virtual page mouse and keyboard."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
        self._browser_name = settings.browser_channel
        self._monitor_rect: Rectangle | None = None
        self._console_errors: list[str] = []
        self._request_failures: list[str] = []

    @property
    def active(self) -> bool:
        return self._page is not None and not self._page.is_closed()

    @property
    def monitor_rect(self) -> Rectangle | None:
        return self._monitor_rect

    @property
    def page(self) -> Any:
        if not self.active:
            raise RuntimeError("The isolated browser has not been started.")
        return self._page

    @staticmethod
    def _channel(browser: str | None) -> str | None:
        value = (browser or "").strip().lower()
        if value in {"chrome", "google chrome"}:
            return "chrome"
        if value in {"edge", "msedge", "microsoft edge"}:
            return "msedge"
        if value in {"chromium", "playwright", ""}:
            return None
        return value

    def start(self, monitor_rect: Rectangle | None, browser: str | None = None) -> None:
        if self.active:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is not installed. Run: python -m pip install -e . && "
                "python -m playwright install chromium"
            ) from exc

        self._playwright = sync_playwright().start()
        channel = self._channel(browser or self.settings.browser_channel)
        self._browser_name = channel or "chromium"
        self._monitor_rect = monitor_rect
        rect = monitor_rect or Rectangle(left=80, top=80, width=1440, height=900)
        width = max(900, rect.width)
        height = max(700, rect.height)
        args = [
            f"--window-position={rect.left},{rect.top}",
            f"--window-size={width},{height}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
        ]
        self.settings.browser_profile_dir.mkdir(parents=True, exist_ok=True)
        kwargs: dict[str, Any] = {
            "user_data_dir": str(self.settings.browser_profile_dir),
            "headless": False,
            "args": args,
            "viewport": {"width": max(800, width - 20), "height": max(560, height - 100)},
            "accept_downloads": True,
        }
        if channel:
            kwargs["channel"] = channel
        try:
            self._context = self._playwright.chromium.launch_persistent_context(**kwargs)
        except Exception as first_error:
            kwargs.pop("channel", None)
            self._browser_name = "chromium"
            try:
                self._context = self._playwright.chromium.launch_persistent_context(**kwargs)
            except Exception as second_error:
                self.close()
                raise RuntimeError(
                    "Could not start the requested browser or Playwright Chromium. Run "
                    "'python -m playwright install chromium'. "
                    f"Errors: {first_error}; {second_error}"
                ) from second_error
        pages = self._context.pages
        self._page = pages[0] if pages else self._context.new_page()
        self._wire_page(self._page)

    def _wire_page(self, page: Any) -> None:
        page.on("console", self._on_console)
        page.on("pageerror", lambda error: self._console_errors.append(str(error)[:1000]))
        page.on(
            "requestfailed",
            lambda request: self._request_failures.append(
                f"{request.method} {request.url}: {request.failure or 'failed'}"[:1200]
            ),
        )
        page.on("popup", self._on_popup)

    def _on_popup(self, page: Any) -> None:
        self._page = page
        self._wire_page(page)

    def _on_console(self, message: Any) -> None:
        if getattr(message, "type", "") == "error":
            self._console_errors.append(str(message.text)[:1000])

    def open_url(self, url: str, monitor_rect: Rectangle | None, browser: str | None = None) -> str:
        self.start(monitor_rect, browser)
        normalized = url.strip()
        if "://" not in normalized:
            normalized = f"https://{normalized}"
        response = None
        try:
            response = self.page.goto(
                normalized,
                wait_until="domcontentloaded",
                timeout=self.settings.browser_timeout_ms,
            )
        except Exception as exc:
            if "Timeout" not in type(exc).__name__ and "Timeout" not in str(exc):
                raise
        status = response.status if response is not None else None
        return f"Opened {self.page.url} in isolated {self._browser_name}" + (
            f" (HTTP {status})." if status is not None else "."
        )

    def capture(self, screenshot_path: Path | None = None) -> BrowserSnapshot:
        page = self.page
        page.wait_for_timeout(100)
        png = page.screenshot(full_page=False, animations="disabled")
        if screenshot_path:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot_path.write_bytes(png)
        image = Image.open(BytesIO(png)).convert("RGB")
        elements, wrappers = self._snapshot_elements(image.width, image.height)
        return BrowserSnapshot(
            title=page.title() or "Untitled page",
            url=page.url,
            image=image,
            image_bytes=png,
            uia=UIASnapshot(elements=elements, wrappers=wrappers),
            viewport=Rectangle(left=0, top=0, width=image.width, height=image.height),
            browser_name=self._browser_name,
        )

    def _snapshot_elements(
        self,
        image_width: int,
        image_height: int,
    ) -> tuple[list[UIElement], dict[str, BrowserElementRef]]:
        raw = self.page.evaluate(
            r"""
            (limit) => {
              const selectors = [
                'a[href]', 'button', 'input', 'textarea', 'select',
                '[role="button"]', '[role="link"]', '[role="textbox"]',
                '[contenteditable="true"]', '[tabindex]:not([tabindex="-1"])'
              ];
              const seen = new Set();
              const output = [];
              for (const el of document.querySelectorAll(selectors.join(','))) {
                if (output.length >= limit) break;
                if (seen.has(el)) continue;
                seen.add(el);
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                if (rect.width < 2 || rect.height < 2) continue;
                if (rect.bottom <= 0 || rect.right <= 0 || rect.top >= innerHeight || rect.left >= innerWidth) continue;
                if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0) continue;
                const id = `B${String(output.length + 1).padStart(3, '0')}`;
                el.setAttribute('data-agent-os-id', id);
                const aria = el.getAttribute('aria-label') || '';
                const placeholder = el.getAttribute('placeholder') || '';
                const value = (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) ? el.value : '';
                const text = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
                const name = (aria || placeholder || text || value || el.getAttribute('title') || el.getAttribute('name') || id).slice(0, 220);
                const role = el.getAttribute('role') || el.tagName.toLowerCase();
                output.push({
                  id, name, role,
                  disabled: Boolean(el.disabled) || el.getAttribute('aria-disabled') === 'true',
                  automationId: el.id || el.getAttribute('name') || null,
                  rect: {
                    left: Math.max(0, Math.round(rect.left)),
                    top: Math.max(0, Math.round(rect.top)),
                    width: Math.max(1, Math.round(Math.min(rect.right, innerWidth) - Math.max(rect.left, 0))),
                    height: Math.max(1, Math.round(Math.min(rect.bottom, innerHeight) - Math.max(rect.top, 0)))
                  }
                });
              }
              return output;
            }
            """,
            self.settings.max_ui_elements,
        )
        elements: list[UIElement] = []
        wrappers: dict[str, BrowserElementRef] = {}
        for item in raw or []:
            rect_data = item.get("rect") or {}
            rect = Rectangle(
                left=int(rect_data.get("left", 0)),
                top=int(rect_data.get("top", 0)),
                width=max(1, int(rect_data.get("width", 1))),
                height=max(1, int(rect_data.get("height", 1))),
            )
            element_id = str(item.get("id"))
            elements.append(
                UIElement(
                    element_id=element_id,
                    name=str(item.get("name") or element_id)[:200],
                    control_type=str(item.get("role") or "element")[:80],
                    automation_id=(
                        str(item.get("automationId"))[:150]
                        if item.get("automationId")
                        else None
                    ),
                    enabled=not bool(item.get("disabled")),
                    visible=True,
                    rect=rect,
                    center_x=max(
                        0,
                        min(1000, round((rect.left + rect.width / 2) * 1000 / image_width)),
                    ),
                    center_y=max(
                        0,
                        min(1000, round((rect.top + rect.height / 2) * 1000 / image_height)),
                    ),
                    source="browser",
                )
            )
            wrappers[element_id] = BrowserElementRef(
                selector=f'[data-agent-os-id="{element_id}"]',
                element_id=element_id,
            )
        return elements, wrappers

    def _locator(self, ref: BrowserElementRef) -> Any:
        return self.page.locator(ref.selector).first

    @staticmethod
    def _key(key: str) -> str:
        mapping = {
            "enter": "Enter",
            "return": "Enter",
            "esc": "Escape",
            "escape": "Escape",
            "tab": "Tab",
            "backspace": "Backspace",
            "delete": "Delete",
            "home": "Home",
            "end": "End",
            "pageup": "PageUp",
            "pagedown": "PageDown",
            "up": "ArrowUp",
            "down": "ArrowDown",
            "left": "ArrowLeft",
            "right": "ArrowRight",
            "space": "Space",
            "ctrl": "Control",
            "control": "Control",
            "alt": "Alt",
            "shift": "Shift",
            "meta": "Meta",
            "win": "Meta",
            "winleft": "Meta",
        }
        normalized = key.strip().lower()
        if normalized in mapping:
            return mapping[normalized]
        if re.fullmatch(r"f\d{1,2}", normalized):
            return normalized.upper()
        return key

    def viewport_screen_rect(self) -> Rectangle:
        """Best-effort physical screen bounds for the browser page viewport."""
        if not self.active:
            rect = self._monitor_rect or Rectangle(left=0, top=0, width=1200, height=800)
            return rect
        try:
            metrics = self.page.evaluate(
                """() => ({
                  screenX: window.screenX, screenY: window.screenY,
                  outerWidth: window.outerWidth, outerHeight: window.outerHeight,
                  innerWidth: window.innerWidth, innerHeight: window.innerHeight
                })"""
            )
            outer_width = max(1, int(metrics.get("outerWidth") or 1))
            outer_height = max(1, int(metrics.get("outerHeight") or 1))
            inner_width = max(1, int(metrics.get("innerWidth") or 1))
            inner_height = max(1, int(metrics.get("innerHeight") or 1))
            side = max(0, (outer_width - inner_width) // 2)
            top_chrome = max(0, outer_height - inner_height - side)
            return Rectangle(
                left=int(metrics.get("screenX") or 0) + side,
                top=int(metrics.get("screenY") or 0) + top_chrome,
                width=inner_width,
                height=inner_height,
            )
        except Exception:
            rect = self._monitor_rect or Rectangle(left=0, top=0, width=1200, height=800)
            return rect

    def screen_point(self, x: int, y: int) -> tuple[int, int]:
        rect = self.viewport_screen_rect()
        return (
            rect.left + round(x * max(1, rect.width - 1) / 1000),
            rect.top + round(y * max(1, rect.height - 1) / 1000),
        )

    def click_point(self, x: int, y: int, click_count: int = 1, button: str = "left") -> str:
        snapshot = self.capture()
        px = round(x * max(1, snapshot.image.width - 1) / 1000)
        py = round(y * max(1, snapshot.image.height - 1) / 1000)
        self.page.mouse.click(px, py, click_count=click_count, button=button)
        return f"Browser {button}-clicked page point ({px}, {py})."

    def move_point(self, x: int, y: int) -> str:
        snapshot = self.capture()
        px = round(x * max(1, snapshot.image.width - 1) / 1000)
        py = round(y * max(1, snapshot.image.height - 1) / 1000)
        self.page.mouse.move(px, py)
        return f"Moved browser virtual pointer to ({px}, {py})."

    def click_element(self, ref: BrowserElementRef) -> str:
        self._locator(ref).click(timeout=self.settings.browser_timeout_ms)
        return f"Clicked browser element {ref.element_id}."

    def fill_element(self, ref: BrowserElementRef, text: str) -> str:
        locator = self._locator(ref)
        try:
            locator.fill(text, timeout=self.settings.browser_timeout_ms)
        except Exception:
            locator.click(timeout=self.settings.browser_timeout_ms)
            self.page.keyboard.insert_text(text)
        return f"Filled browser element {ref.element_id} with {len(text)} characters."

    def type_text(self, text: str) -> str:
        self.page.keyboard.insert_text(text)
        return f"Typed {len(text)} characters with the browser virtual keyboard."

    def press_key(self, key: str) -> str:
        self.page.keyboard.press(self._key(key))
        return f"Pressed browser key {key}."

    def hotkey(self, keys: list[str]) -> str:
        normalized = [key.strip().lower() for key in keys]
        if set(normalized) == {"alt", "left"}:
            self.page.go_back(wait_until="domcontentloaded", timeout=self.settings.browser_timeout_ms)
            return "Navigated browser back."
        combo = "+".join(self._key(key) for key in keys)
        self.page.keyboard.press(combo)
        return f"Pressed browser hotkey {combo}."

    def scroll(self, amount: int) -> str:
        self.page.mouse.wheel(0, -amount * 320)
        return f"Scrolled browser {amount} units."

    def wait(self, seconds: float) -> str:
        self.page.wait_for_timeout(round(seconds * 1000))
        return f"Waited {seconds:.1f} seconds in browser."

    def diagnostics(self, clear: bool = False) -> dict[str, object]:
        data = {
            "url": self.page.url if self.active else None,
            "title": self.page.title() if self.active else None,
            "console_errors": list(self._console_errors),
            "request_failures": list(self._request_failures),
        }
        if clear:
            self._console_errors.clear()
            self._request_failures.clear()
        return data

    def discover_link_inventory(self, same_origin_only: bool = True) -> dict[str, object]:
        return self.page.evaluate(
            r"""
            (sameOriginOnly) => {
              const links = [];
              const seen = new Set();
              let eligibleAnchors = 0;
              let duplicateUrls = 0;
              for (const anchor of document.querySelectorAll('a[href]')) {
                const url = new URL(anchor.href, location.href);
                if (!['http:', 'https:'].includes(url.protocol)) continue;
                if (sameOriginOnly && url.origin !== location.origin) continue;
                eligibleAnchors += 1;
                url.hash = '';
                const href = url.href;
                if (seen.has(href)) {
                  duplicateUrls += 1;
                  continue;
                }
                seen.add(href);
                links.push({
                  url: href,
                  text: (anchor.innerText || anchor.getAttribute('aria-label') || href).replace(/\s+/g, ' ').trim().slice(0, 250)
                });
              }
              return {eligibleAnchors, duplicateUrls, links};
            }
            """,
            same_origin_only,
        )

    def discover_links(self, same_origin_only: bool = True) -> list[dict[str, str]]:
        inventory = self.discover_link_inventory(same_origin_only)
        return list(inventory.get("links") or [])

    @staticmethod
    def _safe_name(index: int, url: str) -> str:
        parsed = urlparse(url)
        text = re.sub(r"[^a-zA-Z0-9]+", "-", f"{parsed.netloc}{parsed.path}").strip("-")
        return f"{index:03d}-{(text or 'page')[:90]}"

    def smoke_test_site(
        self,
        output_dir: Path,
        max_links: int,
    ) -> dict[str, object]:
        output_dir.mkdir(parents=True, exist_ok=True)
        inventory = self.discover_link_inventory(same_origin_only=True)
        all_links = list(inventory.get("links") or [])
        links = all_links[:max_links]
        results: list[dict[str, object]] = []
        for index, link in enumerate(links, start=1):
            url = str(link["url"])
            page = self._context.new_page()
            page_errors: list[str] = []
            request_failures: list[str] = []
            page.on("pageerror", lambda error, bucket=page_errors: bucket.append(str(error)[:1000]))
            page.on(
                "requestfailed",
                lambda request, bucket=request_failures: bucket.append(
                    f"{request.method} {request.url}: {request.failure or 'failed'}"[:1200]
                ),
            )
            status = None
            error = None
            started = time.monotonic()
            try:
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.settings.browser_timeout_ms,
                )
                status = response.status if response is not None else None
                page.wait_for_timeout(150)
            except Exception as exc:
                error = str(exc)[:1200]
            final_url = page.url
            title = ""
            try:
                title = page.title()
            except Exception:
                pass
            visible_error = None
            try:
                body_text = page.locator("body").inner_text(timeout=3000).lower()[:12000]
                for marker in (
                    "internal server error",
                    "application error",
                    "page not found",
                    "404 not found",
                    "something went wrong",
                    "this site can’t be reached",
                    "this site can't be reached",
                ):
                    if marker in body_text:
                        visible_error = marker
                        break
            except Exception:
                pass
            passed = (
                error is None
                and (status is None or status < 400)
                and not page_errors
                and visible_error is None
            )
            screenshot_name = self._safe_name(index, url) + ".png"
            screenshot_path = output_dir / screenshot_name
            try:
                page.screenshot(path=str(screenshot_path), full_page=False, animations="disabled")
            except Exception:
                screenshot_path = Path("")
            results.append(
                {
                    "index": index,
                    "text": link.get("text", ""),
                    "requested_url": url,
                    "final_url": final_url,
                    "status": status,
                    "title": title,
                    "passed": passed,
                    "error": error,
                    "visible_error": visible_error,
                    "page_errors": page_errors,
                    "request_failures": request_failures,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "screenshot": str(screenshot_path) if str(screenshot_path) else None,
                }
            )
            page.close()

        passed_count = sum(1 for item in results if item["passed"])
        report = {
            "start_url": self.page.url,
            "eligible_anchors": int(inventory.get("eligibleAnchors") or 0),
            "unique_links": len(all_links),
            "duplicates_skipped": int(inventory.get("duplicateUrls") or 0),
            "limited_by_max_links": len(all_links) > max_links,
            "max_links": max_links,
            "discovered_links": len(all_links),
            "tested_links": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "results": results,
        }
        report_path = output_dir / "smoke-report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report

    def close(self) -> None:
        context, playwright = self._context, self._playwright
        self._page = None
        self._context = None
        self._playwright = None
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass
