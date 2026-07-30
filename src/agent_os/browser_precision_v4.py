from __future__ import annotations

import re
from contextlib import suppress
from pathlib import Path
from typing import Any

from agent_os.browser import BrowserElementRef, BrowserSnapshot
from agent_os.browser_precision_v3 import BrowserController as BaseBrowserController
from agent_os.models import UIElement


class BrowserController(BaseBrowserController):
    """Render the virtual pointer in-page and provide robust form controls."""

    _CURSOR_HOST_ID = "__windows_agent_cursor_host__"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._virtual_cursor_state: tuple[float, float] | None = None

    def _show_virtual_cursor(self, x: float, y: float, action: str) -> None:
        self.page.evaluate(
            r"""
            ([x, y, action, hostId]) => {
              let host = document.getElementById(hostId);
              if (!host) {
                host = document.createElement('div');
                host.id = hostId;
                host.setAttribute('aria-hidden', 'true');
                Object.assign(host.style, {
                  position: 'fixed',
                  left: '0px',
                  top: '0px',
                  width: '64px',
                  height: '72px',
                  display: 'none',
                  pointerEvents: 'none',
                  userSelect: 'none',
                  zIndex: '2147483647',
                  background: 'transparent',
                  border: '0',
                  margin: '0',
                  padding: '0',
                  contain: 'layout style paint',
                  isolation: 'isolate',
                  transform: 'translate3d(-200px, -200px, 0)',
                  willChange: 'transform',
                });
                const shadow = host.attachShadow({mode: 'open'});
                const style = document.createElement('style');
                style.textContent = `
                  :host { all: initial; }
                  #hand {
                    position: absolute;
                    left: 0;
                    top: 0;
                    width: 58px;
                    height: 66px;
                    display: flex;
                    align-items: flex-start;
                    justify-content: center;
                    overflow: visible;
                    color: initial;
                    background: transparent;
                    border: 0;
                    font-family: "Segoe UI Emoji", "Apple Color Emoji",
                      "Noto Color Emoji", sans-serif;
                    font-size: 46px;
                    font-style: normal;
                    font-weight: normal;
                    line-height: 1;
                    text-shadow:
                      -1px -1px 0 rgba(255,255,255,.95),
                       1px -1px 0 rgba(255,255,255,.95),
                      -1px  1px 0 rgba(255,255,255,.95),
                       1px  1px 0 rgba(255,255,255,.95),
                       0 3px 7px rgba(0,0,0,.45);
                    filter: none;
                    transform: translateZ(0);
                  }
                  #ring {
                    position: absolute;
                    left: 23px;
                    top: 1px;
                    width: 18px;
                    height: 18px;
                    box-sizing: border-box;
                    border: 3px solid #39ff14;
                    border-radius: 999px;
                    opacity: 0;
                    pointer-events: none;
                    background: transparent;
                  }
                `;
                const hand = document.createElement('div');
                hand.id = 'hand';
                hand.textContent = '👆🏻';
                const ring = document.createElement('div');
                ring.id = 'ring';
                shadow.append(style, ring, hand);
                document.documentElement.appendChild(host);
              }

              host.style.display = 'block';
              const target =
                `translate3d(${Math.round(x - 29)}px, ${Math.round(y - 5)}px, 0)`;
              if (host.dataset.ready === '1') {
                host.style.transition =
                  'transform 145ms cubic-bezier(.2,.8,.2,1)';
              } else {
                host.style.transition = 'none';
                host.dataset.ready = '1';
              }
              host.style.transform = target;

              if (String(action).toLowerCase().includes('click')) {
                const ring = host.shadowRoot?.getElementById('ring');
                if (ring) {
                  for (const animation of ring.getAnimations()) animation.cancel();
                  ring.animate(
                    [
                      {opacity: .95, transform: 'scale(.35)'},
                      {opacity: 0, transform: 'scale(1.8)'},
                    ],
                    {duration: 360, easing: 'cubic-bezier(.1,.8,.2,1)'},
                  );
                }
              }
            }
            """,
            [round(x), round(y), action, self._CURSOR_HOST_ID],
        )
        self._virtual_cursor_state = (x, y)

    def _hide_virtual_cursor(self) -> None:
        if not self.active:
            return
        with suppress(Exception):
            self.page.evaluate(
                r"""
                hostId => {
                  const host = document.getElementById(hostId);
                  if (host) host.style.display = 'none';
                }
                """,
                self._CURSOR_HOST_ID,
            )

    def _emit_pointer(self, x: float, y: float, action: str) -> None:
        mode = getattr(self.settings, "cursor_mode", "virtual")
        if mode == "virtual":
            self._show_virtual_cursor(x, y, action)
            return
        self._hide_virtual_cursor()
        super()._emit_pointer(x, y, action)

    def capture(self, screenshot_path: Path | None = None) -> BrowserSnapshot:
        state = self._virtual_cursor_state
        should_restore = state is not None and getattr(
            self.settings, "cursor_mode", "virtual"
        ) == "virtual"
        if should_restore:
            self._hide_virtual_cursor()
        try:
            return super().capture(screenshot_path)
        finally:
            if should_restore and self.active and state is not None:
                with suppress(Exception):
                    self._show_virtual_cursor(state[0], state[1], "restore")

    @staticmethod
    def _normalized(text: str) -> str:
        return " ".join(text.casefold().split())

    def _visible_options(self, limit: int = 80) -> list[tuple[Any, str]]:
        options = self.page.get_by_role("option")
        found: list[tuple[Any, str]] = []
        count = min(options.count(), limit)
        for index in range(count):
            candidate = options.nth(index)
            with suppress(Exception):
                if not candidate.is_visible():
                    continue
                label = (
                    candidate.get_attribute("aria-label")
                    or candidate.inner_text()
                    or candidate.text_content()
                    or ""
                ).strip()
                if label:
                    found.append((candidate, label))
        return found

    def _match_visible_option(self, requested: str) -> tuple[Any | None, list[str]]:
        wanted = self._normalized(requested)
        options = self._visible_options()
        labels = [label for _, label in options]
        exact = [
            candidate
            for candidate, label in options
            if self._normalized(label) == wanted
        ]
        if len(exact) == 1:
            return exact[0], labels
        contains = [
            candidate
            for candidate, label in options
            if wanted in self._normalized(label)
        ]
        if len(contains) == 1:
            return contains[0], labels
        return None, labels

    def open_combobox_state(
        self,
        ref: BrowserElementRef,
        element: UIElement,
    ) -> tuple[str, dict[str, object]]:
        """Open an ARIA combobox once and report its visible options."""

        locator = self._locator(ref)
        locator.scroll_into_view_if_needed(timeout=self.settings.browser_timeout_ms)
        before = locator.get_attribute("aria-expanded")
        before_count = len(self._visible_options())
        method = "click"
        try:
            locator.click(trial=True, timeout=self.settings.browser_timeout_ms)
            locator.click(timeout=self.settings.browser_timeout_ms)
        except Exception:
            locator.focus(timeout=self.settings.browser_timeout_ms)
            locator.press("ArrowDown", timeout=self.settings.browser_timeout_ms)
            method = "ArrowDown"
        self.page.wait_for_timeout(180)
        after = locator.get_attribute("aria-expanded")
        options = [label for _, label in self._visible_options()]
        opened = after == "true" or len(options) > before_count
        if not opened:
            raise RuntimeError(
                f"Combobox {element.name!r} did not open. "
                "Use fill_element with the exact desired option label, or ask the user "
                "for the required option instead of repeating the click."
            )
        return (
            f"Opened combobox {element.name!r} using {method}; "
            f"{len(options)} visible options are available.",
            {
                "element_id": element.element_id,
                "opened": True,
                "aria_expanded_before": before,
                "aria_expanded_after": after,
                "visible_options": options[:40],
                "method": method,
            },
        )

    def select_option_state(
        self,
        ref: BrowserElementRef,
        element: UIElement,
        requested: str,
    ) -> tuple[str, dict[str, object]]:
        """Select a native or ARIA option and verify the resulting value."""

        locator = self._locator(ref)
        locator.scroll_into_view_if_needed(timeout=self.settings.browser_timeout_ms)
        metadata = locator.evaluate(
            r"""
            el => ({
              tag: el.tagName.toLowerCase(),
              role: el.getAttribute('role') || '',
              editable: Boolean(
                el.isContentEditable ||
                ['input', 'textarea'].includes(el.tagName.toLowerCase())
              ),
              expanded: el.hasAttribute('aria-expanded')
                ? el.getAttribute('aria-expanded') === 'true'
                : null,
              value: ('value' in el && typeof el.value === 'string') ? el.value : null,
              text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(),
            })
            """
        )
        tag = str(metadata.get("tag") or "")
        method = ""
        available: list[str] = []

        if tag == "select":
            options = locator.evaluate(
                r"""
                el => Array.from(el.options || []).map(option => ({
                  label: (option.label || option.textContent || '').trim(),
                  value: option.value,
                  disabled: Boolean(option.disabled),
                }))
                """
            )
            wanted = self._normalized(requested)
            usable = [item for item in options if not item.get("disabled")]
            available = [str(item.get("label") or item.get("value") or "") for item in usable]
            exact = [
                item for item in usable
                if self._normalized(str(item.get("label") or "")) == wanted
                or self._normalized(str(item.get("value") or "")) == wanted
            ]
            contains = [
                item for item in usable
                if wanted in self._normalized(str(item.get("label") or ""))
            ]
            match = exact[0] if len(exact) == 1 else (
                contains[0] if len(contains) == 1 else None
            )
            if match is None:
                preview = ", ".join(available[:20]) or "no enabled options"
                raise RuntimeError(
                    f"Could not uniquely match option {requested!r}. Available: {preview}."
                )
            selected_values = locator.select_option(
                value=str(match.get("value") or ""),
                timeout=self.settings.browser_timeout_ms,
            )
            method = "native select_option"
            self.page.wait_for_timeout(100)
            state = locator.evaluate(
                r"""
                el => {
                  const selected = Array.from(el.selectedOptions || []);
                  return {
                    value: el.value,
                    labels: selected.map(
                      option => (option.label || option.textContent || '').trim()
                    ),
                    values: selected.map(option => option.value),
                  };
                }
                """
            )
            selected_labels = [str(item) for item in state.get("labels") or []]
            selected = bool(selected_values) and (
                wanted in {self._normalized(item) for item in selected_labels}
                or wanted == self._normalized(str(state.get("value") or ""))
            )
        else:
            expanded = metadata.get("expanded")
            if expanded is not True:
                try:
                    locator.click(
                        trial=True,
                        timeout=self.settings.browser_timeout_ms,
                    )
                    locator.click(timeout=self.settings.browser_timeout_ms)
                    method = "ARIA option click"
                except Exception:
                    locator.focus(timeout=self.settings.browser_timeout_ms)
                    locator.press("ArrowDown", timeout=self.settings.browser_timeout_ms)
                    method = "ARIA keyboard open"
                self.page.wait_for_timeout(180)

            option, available = self._match_visible_option(requested)
            if option is None and bool(metadata.get("editable")):
                with suppress(Exception):
                    locator.fill(requested, timeout=self.settings.browser_timeout_ms)
                    self.page.wait_for_timeout(180)
                    option, available = self._match_visible_option(requested)

            if option is None:
                preview = ", ".join(available[:20]) or "no visible options"
                raise RuntimeError(
                    f"Could not find visible option {requested!r}. Available: {preview}. "
                    "Scroll the dropdown or ask the user for an exact option label."
                )

            option.scroll_into_view_if_needed(timeout=self.settings.browser_timeout_ms)
            box = option.bounding_box(timeout=self.settings.browser_timeout_ms)
            if box is not None:
                self._move_mouse(
                    float(box["x"]) + float(box["width"]) / 2,
                    float(box["y"]) + float(box["height"]) / 2,
                    "click-option",
                )
            option.click(timeout=self.settings.browser_timeout_ms)
            self.page.wait_for_timeout(140)
            method = method or "ARIA option click"
            selected_state = locator.evaluate(
                r"""
                el => ({
                  value: ('value' in el && typeof el.value === 'string')
                    ? el.value : null,
                  text: (el.innerText || el.textContent || '')
                    .replace(/\s+/g, ' ').trim(),
                  label: el.getAttribute('aria-label') || '',
                  active: el.getAttribute('aria-activedescendant') || '',
                  expanded: el.hasAttribute('aria-expanded')
                    ? el.getAttribute('aria-expanded') === 'true' : null,
                })
                """
            )
            selected_text = " ".join(
                str(selected_state.get(key) or "")
                for key in ("value", "text", "label")
            )
            selected = self._normalized(requested) in self._normalized(selected_text)
            if not selected:
                selected_options = self.page.locator(
                    '[role="option"][aria-selected="true"], option:checked'
                )
                for index in range(min(selected_options.count(), 20)):
                    candidate = selected_options.nth(index)
                    with suppress(Exception):
                        label = (
                            candidate.get_attribute("aria-label")
                            or candidate.inner_text()
                            or candidate.text_content()
                            or ""
                        )
                        if self._normalized(label) == self._normalized(requested):
                            selected = True
                            break
            state = {
                "value": selected_state.get("value"),
                "labels": [requested] if selected else [],
                "expanded": selected_state.get("expanded"),
            }

        if not selected:
            raise RuntimeError(
                f"The control did not confirm selection of {requested!r}. "
                "Do not repeatedly click the combobox; inspect its visible options."
            )

        return (
            f"Selected {requested!r} in browser element {element.element_id} "
            f"using {method}.",
            {
                "element_id": element.element_id,
                "requested_option": requested,
                "selected": True,
                "method": method,
                "available_options": available[:30],
                "selection_state": state,
            },
        )

    def _prepare_scroll_target(
        self,
        ref: BrowserElementRef | None,
        direction: int,
    ) -> dict[str, object]:
        selector = ref.selector if ref is not None else None
        return self.page.evaluate(
            r"""
            ([selector, direction]) => {
              const canScroll = (el) => {
                if (!el) return false;
                const style = getComputedStyle(el);
                const overflow = style.overflowY;
                return el.scrollHeight > el.clientHeight + 3 &&
                  ['auto', 'scroll', 'overlay'].includes(overflow);
              };
              const canMove = (el) => direction > 0
                ? el.scrollTop < el.scrollHeight - el.clientHeight - 2
                : el.scrollTop > 2;
              const nearest = (start) => {
                let node = start;
                while (node && node !== document.body && node !== document.documentElement) {
                  if (canScroll(node) && canMove(node)) return node;
                  node = node.parentElement;
                }
                return null;
              };
              let origin = selector ? document.querySelector(selector) : document.activeElement;
              let target = nearest(origin);
              if (!target) {
                const candidates = Array.from(document.querySelectorAll('body *'))
                  .filter(el => {
                    if (!canScroll(el) || !canMove(el)) return false;
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    return rect.width > 80 && rect.height > 80 &&
                      rect.bottom > 0 && rect.right > 0 &&
                      rect.top < innerHeight && rect.left < innerWidth &&
                      style.visibility !== 'hidden' && style.display !== 'none';
                  })
                  .sort((a, b) => {
                    const ar = a.getBoundingClientRect();
                    const br = b.getBoundingClientRect();
                    return (br.width * br.height) - (ar.width * ar.height);
                  });
                target = candidates[0] || null;
              }
              const documentTarget =
                document.scrollingElement || document.documentElement;
              if (!target) target = documentTarget;
              window.__windowsAgentScrollTarget = target;
              const rect = target === documentTarget
                ? {left: 0, top: 0, width: innerWidth, height: innerHeight}
                : target.getBoundingClientRect();
              const label = target === documentTarget
                ? 'document'
                : (
                    target.getAttribute('aria-label') ||
                    target.getAttribute('role') ||
                    target.id ||
                    target.className ||
                    target.tagName
                  ).toString().replace(/\s+/g, ' ').trim().slice(0, 160);
              return {
                label,
                document: target === documentTarget,
                left: rect.left,
                top: rect.top,
                width: rect.width,
                height: rect.height,
                before: target.scrollTop,
                maximum: Math.max(0, target.scrollHeight - target.clientHeight),
              };
            }
            """,
            [selector, direction],
        )

    def _read_scroll_target(self) -> dict[str, object]:
        return self.page.evaluate(
            r"""
            () => {
              const target = window.__windowsAgentScrollTarget ||
                document.scrollingElement || document.documentElement;
              const documentTarget =
                document.scrollingElement || document.documentElement;
              return {
                after: target.scrollTop,
                maximum: Math.max(0, target.scrollHeight - target.clientHeight),
                document: target === documentTarget,
              };
            }
            """
        )

    def _fallback_scroll(self, delta: int) -> None:
        self.page.evaluate(
            r"""
            delta => {
              const target = window.__windowsAgentScrollTarget ||
                document.scrollingElement || document.documentElement;
              target.scrollTop = target.scrollTop + delta;
            }
            """,
            delta,
        )

    def scroll_state(
        self,
        amount: int,
        ref: BrowserElementRef | None = None,
    ) -> tuple[str, dict[str, object]]:
        """Wheel-scroll the correct container and verify observed movement."""

        if amount == 0:
            raise RuntimeError("Scroll amount must be positive or negative.")
        direction = 1 if amount > 0 else -1
        target = self._prepare_scroll_target(ref, direction)
        metrics = self._viewport_metrics()
        viewport_width = max(1, int(metrics.get("innerWidth") or 1))
        viewport_height = max(1, int(metrics.get("innerHeight") or 1))
        unit = min(
            max(160, self.settings.browser_scroll_pixels),
            max(160, round(viewport_height * 0.82)),
        )
        delta = int(amount * unit)
        left = float(target.get("left") or 0)
        top = float(target.get("top") or 0)
        width = max(1.0, float(target.get("width") or 1))
        height = max(1.0, float(target.get("height") or 1))
        x = min(max(1.0, left + width / 2), max(1.0, viewport_width - 2))
        y = min(max(1.0, top + height / 2), max(1.0, viewport_height - 2))
        self._move_mouse(x, y, "scroll")
        self.page.mouse.wheel(0, delta)
        self.page.wait_for_timeout(220)
        after = self._read_scroll_target()
        before_value = int(float(target.get("before") or 0))
        after_value = int(float(after.get("after") or 0))
        method = "mouse wheel"
        if after_value == before_value:
            self._fallback_scroll(delta)
            self.page.wait_for_timeout(120)
            after = self._read_scroll_target()
            after_value = int(float(after.get("after") or 0))
            method = "wheel plus DOM fallback"

        moved = after_value - before_value
        maximum = int(float(after.get("maximum") or target.get("maximum") or 0))
        at_start = after_value <= 1
        at_end = after_value >= max(0, maximum - 1)
        direction_name = "down" if amount > 0 else "up"
        label = str(target.get("label") or "document")
        summary = (
            f"Scrolled {label} {direction_name}: requested {delta} CSS pixels, "
            f"observed {moved} using {method}."
        )
        return (
            summary,
            {
                "scroll_target": label,
                "requested_pixels": delta,
                "observed_pixels": moved,
                "before": before_value,
                "after": after_value,
                "maximum": maximum,
                "at_start": at_start,
                "at_end": at_end,
                "method": method,
            },
        )

    def close(self, force: bool = False) -> None:
        self._virtual_cursor_state = None
        super().close(force=force)


__all__ = ["BrowserController"]
