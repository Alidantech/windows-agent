from __future__ import annotations

import math
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from agent_os.browser import BrowserElementRef, BrowserSnapshot
from agent_os.browser_runtime import BrowserController as BaseBrowserController
from agent_os.models import Rectangle, UIElement
from agent_os.windows import UIASnapshot


class BrowserController(BaseBrowserController):
    """DPI-safe browser grounding and precise virtual input."""

    def __init__(self, settings, cancellation) -> None:
        super().__init__(settings, cancellation)
        self._mouse_css = (0.0, 0.0)
        self._pointer_sink: Callable[[int, int, str], None] | None = None

    def set_pointer_sink(
        self,
        sink: Callable[[int, int, str], None] | None,
    ) -> None:
        self._pointer_sink = sink

    def start(self, monitor_rect: Rectangle | None, browser: str | None = None) -> None:
        if self.active:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is not installed. Run `uv sync` and "
                "`uv run playwright install chromium`."
            ) from exc

        self._playwright = sync_playwright().start()
        channel = self._channel(browser or self.settings.browser_channel)
        self._browser_name = channel or "chromium"
        self._monitor_rect = monitor_rect
        rect = monitor_rect or Rectangle(left=80, top=80, width=1440, height=900)
        args = [
            f"--window-position={rect.left},{rect.top}",
            f"--window-size={rect.width},{rect.height}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            "--disable-features=CalculateNativeWinOcclusion",
        ]
        self.settings.browser_profile_dir.mkdir(parents=True, exist_ok=True)
        kwargs: dict[str, Any] = {
            "user_data_dir": str(self.settings.browser_profile_dir),
            "headless": False,
            "args": args,
            "no_viewport": True,
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
                self.close(force=True)
                raise RuntimeError(
                    "Could not start Chrome or Playwright Chromium. Run "
                    "`uv run playwright install chromium`. "
                    f"Errors: {first_error}; {second_error}"
                ) from second_error
        pages = self._context.pages
        self._page = pages[0] if pages else self._context.new_page()
        self._wire_page(self._page)
        self._context.set_default_timeout(self.settings.browser_timeout_ms)
        self._position_window(rect)

    def _position_window(self, rect: Rectangle) -> None:
        try:
            session = self._context.new_cdp_session(self.page)
            window_id = int(session.send("Browser.getWindowForTarget")["windowId"])
            session.send(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": {
                        "left": rect.left,
                        "top": rect.top,
                        "width": rect.width,
                        "height": rect.height,
                        "windowState": "normal",
                    },
                },
            )
            session.detach()
            self.page.wait_for_timeout(180)
        except Exception:
            pass

    def _bring_to_front(self) -> None:
        try:
            self.page.bring_to_front()
            self.page.wait_for_timeout(30)
        except Exception:
            pass

    def _viewport_metrics(self) -> dict[str, float]:
        return self.page.evaluate(
            """() => ({
              screenX: window.screenX, screenY: window.screenY,
              outerWidth: window.outerWidth, outerHeight: window.outerHeight,
              innerWidth: window.innerWidth, innerHeight: window.innerHeight,
              devicePixelRatio: window.devicePixelRatio || 1
            })"""
        )

    def capture(self, screenshot_path: Path | None = None) -> BrowserSnapshot:
        self._bring_to_front()
        png = self.page.screenshot(
            full_page=False,
            animations="disabled",
            scale="css",
        )
        if screenshot_path:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot_path.write_bytes(png)
        image = Image.open(BytesIO(png)).convert("RGB")
        elements, wrappers = self._snapshot_elements(image.width, image.height)
        return BrowserSnapshot(
            title=self.page.title() or "Untitled page",
            url=self.page.url,
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
                'a[href]', 'button', 'input', 'textarea', 'select', 'option',
                'label[for]', '[role="button"]', '[role="link"]',
                '[role="textbox"]', '[role="combobox"]', '[role="option"]',
                '[role="listbox"]', '[role="menuitem"]', '[role="checkbox"]',
                '[role="radio"]', '[role="switch"]', '[role="tab"]',
                '[role="treeitem"]', '[contenteditable="true"]',
                '[tabindex]:not([tabindex="-1"])', '[onclick]'
              ];
              const state = window.__windowsAgentState ||
                (window.__windowsAgentState = {nextId: 1});
              const output = [];
              const seen = new Set();
              for (const el of document.querySelectorAll(selectors.join(','))) {
                if (output.length >= limit) break;
                if (seen.has(el)) continue;
                seen.add(el);
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                if (rect.width < 2 || rect.height < 2) continue;
                if (rect.bottom <= 0 || rect.right <= 0 ||
                    rect.top >= innerHeight || rect.left >= innerWidth) continue;
                if (style.visibility === 'hidden' || style.display === 'none' ||
                    Number(style.opacity) <= 0.01) continue;
                let id = el.getAttribute('data-windows-agent-id');
                if (!id) {
                  id = `B${String(state.nextId++).padStart(4, '0')}`;
                  el.setAttribute('data-windows-agent-id', id);
                }
                const labels = el.labels ? Array.from(el.labels)
                  .map(label => label.innerText || label.textContent || '').join(' ') : '';
                const labelledBy = (el.getAttribute('aria-labelledby') || '')
                  .split(/\s+/).filter(Boolean)
                  .map(value => document.getElementById(value)?.innerText ||
                    document.getElementById(value)?.textContent || '').join(' ');
                const aria = el.getAttribute('aria-label') || '';
                const placeholder = el.getAttribute('placeholder') || '';
                const text = (el.innerText || el.textContent || '')
                  .replace(/\s+/g, ' ').trim();
                const fieldName = el.getAttribute('name') || '';
                const name = (aria || labelledBy || labels || placeholder || text ||
                  el.getAttribute('title') || fieldName || id)
                  .replace(/\s+/g, ' ').trim().slice(0, 220);
                const tag = el.tagName.toLowerCase();
                const explicitRole = el.getAttribute('role') || '';
                const inputType = tag === 'input' ?
                  (el.getAttribute('type') || 'text').toLowerCase() : null;
                let role = explicitRole || tag;
                if (!explicitRole && tag === 'input') {
                  role = ['checkbox', 'radio', 'button', 'submit'].includes(inputType) ?
                    inputType : 'textbox';
                }
                const left = Math.max(0, rect.left);
                const top = Math.max(0, rect.top);
                const right = Math.min(innerWidth, rect.right);
                const bottom = Math.min(innerHeight, rect.bottom);
                const cx = Math.min(innerWidth - 1, Math.max(0, (left + right) / 2));
                const cy = Math.min(innerHeight - 1, Math.max(0, (top + bottom) / 2));
                const hit = document.elementFromPoint(cx, cy);
                const receivesEvents = Boolean(hit &&
                  (hit === el || el.contains(hit) || hit.contains(el)));
                output.push({
                  id, name, role, tag, inputType, placeholder,
                  href: tag === 'a' ? el.href : null,
                  disabled: Boolean(el.disabled) || el.getAttribute('aria-disabled') === 'true',
                  automationId: el.id || fieldName || null,
                  editable: !el.readOnly && !el.disabled &&
                    (tag === 'input' || tag === 'textarea' || el.isContentEditable ||
                     explicitRole === 'textbox' || explicitRole === 'combobox'),
                  required: Boolean(el.required) || el.getAttribute('aria-required') === 'true',
                  readonly: Boolean(el.readOnly) || el.getAttribute('aria-readonly') === 'true',
                  checked: typeof el.checked === 'boolean' ? el.checked : null,
                  selected: typeof el.selected === 'boolean' ? el.selected : null,
                  focused: document.activeElement === el,
                  receivesEvents,
                  rect: {
                    left: Math.round(left), top: Math.round(top),
                    width: Math.max(1, Math.round(right - left)),
                    height: Math.max(1, Math.round(bottom - top))
                  }
                });
              }
              output.sort((a, b) => {
                if (a.focused !== b.focused) return a.focused ? -1 : 1;
                if (a.disabled !== b.disabled) return a.disabled ? 1 : -1;
                if (a.rect.top !== b.rect.top) return a.rect.top - b.rect.top;
                return a.rect.left - b.rect.left;
              });
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
                        if item.get("automationId") else None
                    ),
                    enabled=not bool(item.get("disabled")),
                    visible=True,
                    rect=rect,
                    center_x=max(0, min(1000, round(
                        (rect.left + rect.width / 2) * 1000 / max(1, image_width)
                    ))),
                    center_y=max(0, min(1000, round(
                        (rect.top + rect.height / 2) * 1000 / max(1, image_height)
                    ))),
                    source="browser",
                    tag=str(item.get("tag") or "") or None,
                    input_type=str(item.get("inputType") or "") or None,
                    placeholder=str(item.get("placeholder") or "") or None,
                    href=str(item.get("href") or "") or None,
                    editable=bool(item.get("editable")),
                    required=bool(item.get("required")),
                    readonly=bool(item.get("readonly")),
                    checked=item.get("checked"),
                    selected=item.get("selected"),
                    focused=bool(item.get("focused")),
                    receives_events=bool(item.get("receivesEvents")),
                )
            )
            wrappers[element_id] = BrowserElementRef(
                selector=f'[data-windows-agent-id="{element_id}"]',
                element_id=element_id,
            )
        return elements, wrappers

    def _css_point(self, x: int, y: int) -> tuple[float, float]:
        metrics = self._viewport_metrics()
        width = max(1.0, float(metrics.get("innerWidth") or 1))
        height = max(1.0, float(metrics.get("innerHeight") or 1))
        return (
            x * max(1.0, width - 1.0) / 1000.0,
            y * max(1.0, height - 1.0) / 1000.0,
        )

    def _emit_pointer(self, x: float, y: float, action: str) -> None:
        if self._pointer_sink is None:
            return
        viewport = self.viewport_screen_rect()
        self._pointer_sink(viewport.left + round(x), viewport.top + round(y), action)

    def _move_mouse(self, x: float, y: float, action: str = "move") -> None:
        self._bring_to_front()
        start_x, start_y = self._mouse_css
        distance = math.hypot(x - start_x, y - start_y)
        steps = max(3, min(24, round(distance / 45)))
        self._emit_pointer(x, y, action)
        for index in range(1, steps + 1):
            progress = index / steps
            eased = 1.0 - (1.0 - progress) ** 3
            self.page.mouse.move(
                start_x + (x - start_x) * eased,
                start_y + (y - start_y) * eased,
            )
            self.page.wait_for_timeout(10)
        self._mouse_css = (x, y)

    def click_point(
        self,
        x: int,
        y: int,
        click_count: int = 1,
        button: str = "left",
    ) -> str:
        px, py = self._css_point(x, y)
        self._move_mouse(px, py, "double-click" if click_count == 2 else "click")
        self.page.mouse.click(px, py, click_count=click_count, button=button, delay=45)
        return f"Browser {button}-clicked CSS point ({round(px)}, {round(py)})."

    def move_point(self, x: int, y: int) -> str:
        px, py = self._css_point(x, y)
        self._move_mouse(px, py)
        return f"Moved browser virtual pointer to CSS point ({round(px)}, {round(py)})."

    def click_element(self, ref: BrowserElementRef) -> str:
        locator = self._locator(ref)
        locator.scroll_into_view_if_needed(timeout=self.settings.browser_timeout_ms)
        locator.click(trial=True, timeout=self.settings.browser_timeout_ms)
        box = locator.bounding_box(timeout=self.settings.browser_timeout_ms)
        if box is None:
            raise RuntimeError(f"Browser element {ref.element_id} has no actionable bounds.")
        x = float(box["x"]) + float(box["width"]) / 2
        y = float(box["y"]) + float(box["height"]) / 2
        self._move_mouse(x, y, "click-element")
        locator.click(timeout=self.settings.browser_timeout_ms)
        return f"Clicked browser element {ref.element_id} at CSS point ({round(x)}, {round(y)})."

    def fill_element(self, ref: BrowserElementRef, text: str) -> str:
        locator = self._locator(ref)
        locator.scroll_into_view_if_needed(timeout=self.settings.browser_timeout_ms)
        locator.focus(timeout=self.settings.browser_timeout_ms)
        box = locator.bounding_box(timeout=self.settings.browser_timeout_ms)
        if box is not None:
            self._move_mouse(
                float(box["x"]) + float(box["width"]) / 2,
                float(box["y"]) + float(box["height"]) / 2,
                "fill-element",
            )
        try:
            locator.fill(text, timeout=self.settings.browser_timeout_ms)
            method = "fill"
        except Exception:
            locator.click(timeout=self.settings.browser_timeout_ms)
            locator.press("Control+A")
            locator.press_sequentially(text, delay=12)
            method = "sequential keyboard"
        return (
            f"Filled browser element {ref.element_id} with {len(text)} characters "
            f"using {method}."
        )

    def type_text(self, text: str) -> str:
        focused = self.page.locator(":focus")
        if focused.count() == 1:
            focused.press_sequentially(text, delay=12)
        else:
            self.page.keyboard.insert_text(text)
        return f"Typed {len(text)} characters with the browser virtual keyboard."

    def scroll(self, amount: int) -> str:
        metrics = self._viewport_metrics()
        x = float(metrics.get("innerWidth") or 1) / 2
        y = float(metrics.get("innerHeight") or 1) / 2
        self._move_mouse(x, y, "scroll")
        before = float(self.page.evaluate("() => window.scrollY"))
        delta = amount * self.settings.browser_scroll_pixels
        self.page.mouse.wheel(0, delta)
        self.page.wait_for_timeout(160)
        after = float(self.page.evaluate("() => window.scrollY"))
        direction = "down" if amount > 0 else "up"
        return (
            f"Scrolled browser {direction} with the virtual mouse wheel "
            f"({delta} CSS pixels requested, {round(after - before)} observed)."
        )

    def viewport_screen_rect(self) -> Rectangle:
        if not self.active:
            return self._monitor_rect or Rectangle(left=0, top=0, width=1200, height=800)
        try:
            metrics = self._viewport_metrics()
            outer_width = max(1.0, float(metrics.get("outerWidth") or 1))
            outer_height = max(1.0, float(metrics.get("outerHeight") or 1))
            inner_width = max(1.0, float(metrics.get("innerWidth") or 1))
            inner_height = max(1.0, float(metrics.get("innerHeight") or 1))
            side = max(0.0, (outer_width - inner_width) / 2)
            top_chrome = max(0.0, outer_height - inner_height - side)
            dpr = max(0.5, float(metrics.get("devicePixelRatio") or 1))
            raw = Rectangle(
                left=round(float(metrics.get("screenX") or 0) + side),
                top=round(float(metrics.get("screenY") or 0) + top_chrome),
                width=round(inner_width),
                height=round(inner_height),
            )
            scaled = Rectangle(
                left=round((float(metrics.get("screenX") or 0) + side) * dpr),
                top=round((float(metrics.get("screenY") or 0) + top_chrome) * dpr),
                width=round(inner_width * dpr),
                height=round(inner_height * dpr),
            )
            monitor = self._monitor_rect
            if monitor is None:
                return scaled if dpr != 1 else raw

            def score(candidate: Rectangle) -> float:
                return (
                    candidate.intersection_area(monitor)
                    - abs(candidate.width - monitor.width) * 200
                    - abs(candidate.height - monitor.height) * 200
                )

            return max((raw, scaled), key=score)
        except Exception:
            return self._monitor_rect or Rectangle(left=0, top=0, width=1200, height=800)


__all__ = ["BrowserController"]
