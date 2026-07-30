from __future__ import annotations

import math
import re
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from agent_os.browser import BrowserElementRef, BrowserSnapshot
from agent_os.browser_precision_v4 import BrowserController as BaseBrowserController
from agent_os.models import UIElement


@dataclass(frozen=True)
class SemanticBrowserElementRef(BrowserElementRef):
    """A compact model handle backed by current semantic locator information."""

    role: str | None = None
    name: str | None = None
    tag: str | None = None
    automation_id: str | None = None
    placeholder: str | None = None
    input_type: str | None = None
    form_id: str | None = None
    occurrence: int = 1


class BrowserController(BaseBrowserController):
    """Self-healing semantic browser control with full-page context telemetry."""

    _SCROLL_HUD_ID = "__windows_agent_scroll_hud__"
    _ROLE_MAP = {
        "a": "link",
        "input": "textbox",
        "textarea": "textbox",
        "select": "combobox",
        "submit": "button",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._semantic_ids: dict[str, str] = {}
        self._next_semantic_id = 1

    @staticmethod
    def _clean(value: str | None) -> str:
        return re.sub(r"\s+", " ", (value or "").casefold()).strip()

    @staticmethod
    def _css_attr(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _semantic_fingerprint(self, element: UIElement, occurrence: int) -> str:
        parts = (
            self.page.url.split("#", 1)[0],
            element.form_id or "",
            element.control_type,
            element.name,
            element.automation_id or "",
            element.tag or "",
            element.input_type or "",
            element.placeholder or "",
            element.href or "",
            str(occurrence),
        )
        return "|".join(self._clean(part) for part in parts)

    def _stable_id(self, fingerprint: str) -> str:
        existing = self._semantic_ids.get(fingerprint)
        if existing:
            return existing
        element_id = f"E{self._next_semantic_id:04d}"
        self._next_semantic_id += 1
        self._semantic_ids[fingerprint] = element_id
        return element_id

    def _snapshot_elements(self, image_width: int, image_height: int):
        elements, wrappers = super()._snapshot_elements(image_width, image_height)
        occurrences: dict[str, int] = {}
        semantic_wrappers: dict[str, SemanticBrowserElementRef] = {}
        for element in elements:
            old_id = element.element_id
            old_ref = wrappers.get(old_id)
            base = "|".join(
                self._clean(part)
                for part in (
                    element.form_id or "",
                    element.control_type,
                    element.name,
                    element.automation_id or "",
                    element.tag or "",
                    element.input_type or "",
                    element.placeholder or "",
                    element.href or "",
                )
            )
            occurrence = occurrences.get(base, 0) + 1
            occurrences[base] = occurrence
            stable_id = self._stable_id(self._semantic_fingerprint(element, occurrence))
            element.element_id = stable_id
            semantic_wrappers[stable_id] = SemanticBrowserElementRef(
                selector=old_ref.selector if old_ref is not None else "",
                element_id=stable_id,
                role=element.control_type,
                name=element.name,
                tag=element.tag,
                automation_id=element.automation_id,
                placeholder=element.placeholder,
                input_type=element.input_type,
                form_id=element.form_id,
                occurrence=occurrence,
            )
        return elements, semantic_wrappers

    def _candidate_locators(self, ref: SemanticBrowserElementRef) -> list[tuple[str, Any]]:
        candidates: list[tuple[str, Any]] = []
        name = (ref.name or "").strip()
        automation_id = (ref.automation_id or "").strip()
        role = self._ROLE_MAP.get(self._clean(ref.role), self._clean(ref.role))

        if automation_id:
            escaped = self._css_attr(automation_id)
            candidates.append(("id", self.page.locator(f'[id="{escaped}"]')))
            candidates.append(("name", self.page.locator(f'[name="{escaped}"]')))
        if ref.selector:
            candidates.append(("captured-selector", self.page.locator(ref.selector)))
        if name:
            with suppress(Exception):
                candidates.append(("label", self.page.get_by_label(name, exact=True)))
            if role:
                with suppress(Exception):
                    candidates.append(
                        ("role+name", self.page.get_by_role(role, name=name, exact=True))
                    )
            if role in {"button", "link", "option", "menuitem", "tab"}:
                with suppress(Exception):
                    candidates.append(("text", self.page.get_by_text(name, exact=True)))
        if ref.placeholder:
            with suppress(Exception):
                candidates.append(
                    ("placeholder", self.page.get_by_placeholder(ref.placeholder, exact=True))
                )
        return candidates

    @staticmethod
    def _visible_matches(locator: Any, limit: int = 12) -> list[Any]:
        matches: list[Any] = []
        for index in range(min(locator.count(), limit)):
            candidate = locator.nth(index)
            with suppress(Exception):
                if candidate.is_visible():
                    matches.append(candidate)
        return matches

    def _locator(self, ref: BrowserElementRef) -> Any:
        if not isinstance(ref, SemanticBrowserElementRef):
            return super()._locator(ref)
        attempted: list[str] = []
        for label, locator in self._candidate_locators(ref):
            attempted.append(label)
            with suppress(Exception):
                visible = self._visible_matches(locator)
                if len(visible) == 1:
                    return visible[0]
                if len(visible) >= ref.occurrence:
                    return visible[ref.occurrence - 1]
                if locator.count() == 1:
                    return locator.first
        raise RuntimeError(
            f"Could not re-resolve semantic element {ref.element_id} "
            f"({ref.role!r} {ref.name!r}). Tried: {', '.join(attempted) or 'none'}. "
            "The page changed materially; capture a fresh semantic map."
        )

    def semantic_page_state(self) -> dict[str, object]:
        return self.page.evaluate(
            r"""
            () => {
              const clean = value => String(value || '').replace(/\s+/g, ' ').trim();
              const nameOf = el => {
                const labels = el.labels ? Array.from(el.labels)
                  .map(label => clean(label.innerText || label.textContent)).join(' ') : '';
                const labelledBy = clean(el.getAttribute('aria-labelledby')).split(' ')
                  .filter(Boolean).map(id => clean(document.getElementById(id)?.innerText ||
                    document.getElementById(id)?.textContent)).filter(Boolean).join(' ');
                return clean(el.getAttribute('aria-label') || labelledBy || labels ||
                  el.getAttribute('placeholder') || el.getAttribute('title') ||
                  el.getAttribute('name') || el.innerText || el.textContent || el.tagName);
              };
              const rendered = el => {
                const style = getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden' &&
                  Number(style.opacity) > 0.01 && rect.width > 1 && rect.height > 1;
              };
              const relation = rect => rect.bottom <= 0 ? 'above' :
                rect.top >= innerHeight ? 'below' : 'visible';
              const roleOf = el => el.getAttribute('role') || (() => {
                const tag = el.tagName.toLowerCase();
                if (tag === 'a') return 'link';
                if (tag === 'select') return 'combobox';
                if (tag === 'textarea') return 'textbox';
                if (tag === 'input') {
                  const type = (el.type || 'text').toLowerCase();
                  return ['checkbox', 'radio', 'button', 'submit'].includes(type)
                    ? type : 'textbox';
                }
                return tag;
              })();
              const documentTarget = document.scrollingElement || document.documentElement;
              const maximum = Math.max(0, documentTarget.scrollHeight - documentTarget.clientHeight);
              const top = documentTarget.scrollTop;
              const depth = maximum > 0 ? Math.round((top / maximum) * 1000) / 10 : 100;
              const selectors = [
                'a[href]', 'button', 'input', 'textarea', 'select',
                '[role="button"]', '[role="link"]', '[role="textbox"]',
                '[role="combobox"]', '[role="option"]', '[role="listbox"]',
                '[role="menuitem"]', '[role="checkbox"]', '[role="radio"]',
                '[role="switch"]', '[role="tab"]', '[contenteditable="true"]',
                '[tabindex]:not([tabindex="-1"])', '[onclick]'
              ].join(',');
              const actionables = [];
              const counts = {above: 0, visible: 0, below: 0};
              for (const el of document.querySelectorAll(selectors)) {
                if (!rendered(el)) continue;
                const rect = el.getBoundingClientRect();
                const where = relation(rect);
                counts[where] += 1;
                if (actionables.length >= 220) continue;
                const rawValue = ('value' in el && typeof el.value === 'string')
                  ? el.value : (el.isContentEditable ? (el.innerText || '') : '');
                actionables.push({
                  role: roleOf(el),
                  name: nameOf(el).slice(0, 180),
                  relation: where,
                  documentY: Math.round(rect.top + top),
                  required: Boolean(el.required) || el.getAttribute('aria-required') === 'true',
                  enabled: !Boolean(el.disabled) && el.getAttribute('aria-disabled') !== 'true',
                  expanded: el.hasAttribute('aria-expanded')
                    ? el.getAttribute('aria-expanded') === 'true' : null,
                  checked: typeof el.checked === 'boolean' ? el.checked : null,
                  selected: typeof el.selected === 'boolean' ? el.selected : null,
                  hasValue: Boolean(String(rawValue || '').trim()),
                });
              }
              const headings = Array.from(document.querySelectorAll(
                'h1,h2,h3,h4,h5,h6,[role="heading"]'
              )).filter(rendered).map(el => {
                const rect = el.getBoundingClientRect();
                return {
                  level: Number(el.getAttribute('aria-level') || el.tagName.slice(1) || 0),
                  text: nameOf(el).slice(0, 180),
                  relation: relation(rect),
                  documentY: Math.round(rect.top + top),
                };
              }).filter(item => item.text).slice(0, 80);
              const canScroll = el => {
                const style = getComputedStyle(el);
                return el.scrollHeight > el.clientHeight + 3 &&
                  ['auto', 'scroll', 'overlay'].includes(style.overflowY);
              };
              const scrollContainers = Array.from(document.querySelectorAll('body *'))
                .filter(el => rendered(el) && canScroll(el)).map(el => {
                  const rect = el.getBoundingClientRect();
                  const max = Math.max(0, el.scrollHeight - el.clientHeight);
                  return {
                    name: nameOf(el).slice(0, 120),
                    role: el.getAttribute('role') || el.tagName.toLowerCase(),
                    top: Math.round(el.scrollTop), maximum: Math.round(max),
                    depthPercent: max > 0
                      ? Math.round((el.scrollTop / max) * 1000) / 10 : 100,
                    visibleArea: Math.round(rect.width * rect.height),
                  };
                }).sort((a, b) => b.visibleArea - a.visibleArea).slice(0, 12);
              return {
                document: {
                  scrollTop: Math.round(top), maximum: Math.round(maximum),
                  depthPercent: depth, viewportHeight: innerHeight,
                  contentHeight: documentTarget.scrollHeight,
                  canScrollUp: top > 1, canScrollDown: top < maximum - 1,
                },
                actionableCounts: counts, headings, actionables, scrollContainers,
              };
            }
            """
        )

    def _aria_snapshot(self) -> str | None:
        body = self.page.locator("body")
        with suppress(Exception):
            return str(body.aria_snapshot(timeout=2500))[:16000]
        with suppress(Exception):
            return str(body.aria_snapshot())[:16000]
        return None

    def _update_scroll_hud(
        self,
        label: str = "Page",
        position: int | None = None,
        maximum: int | None = None,
    ) -> None:
        with suppress(Exception):
            self.page.evaluate(
                r"""
                ([hostId, label, suppliedPosition, suppliedMaximum]) => {
                  const doc = document.scrollingElement || document.documentElement;
                  const position = suppliedPosition == null ? doc.scrollTop : suppliedPosition;
                  const maximum = suppliedMaximum == null
                    ? Math.max(0, doc.scrollHeight - doc.clientHeight) : suppliedMaximum;
                  const percent = maximum > 0
                    ? Math.max(0, Math.min(100, (position / maximum) * 100)) : 100;
                  let host = document.getElementById(hostId);
                  if (!host) {
                    host = document.createElement('div');
                    host.id = hostId;
                    host.setAttribute('aria-hidden', 'true');
                    Object.assign(host.style, {
                      position:'fixed', right:'8px', top:'50%', width:'58px', height:'220px',
                      transform:'translateY(-50%)', zIndex:'2147483646', pointerEvents:'none',
                      background:'transparent', border:'0', margin:'0', padding:'0',
                      contain:'layout style paint', isolation:'isolate'
                    });
                    const shadow = host.attachShadow({mode:'open'});
                    shadow.innerHTML = `
                      <style>
                        :host{all:initial} #panel{box-sizing:border-box;width:58px;height:220px;
                        padding:7px 5px;border:1px solid rgba(255,255,255,.78);border-radius:12px;
                        background:rgba(12,18,30,.82);color:white;font:11px/1.2 Segoe UI,sans-serif;
                        box-shadow:0 3px 12px rgba(0,0,0,.35)} #label{overflow:hidden;
                        text-overflow:ellipsis;white-space:nowrap;text-align:center;margin-bottom:5px}
                        #track{position:relative;width:10px;height:160px;margin:0 auto;border-radius:8px;
                        background:rgba(255,255,255,.18)} #thumb{position:absolute;left:1px;width:8px;
                        height:26px;border-radius:8px;background:#39ff14;
                        box-shadow:0 0 6px rgba(57,255,20,.8)} #percent{text-align:center;
                        margin-top:6px;font-weight:700}
                      </style><div id="panel"><div id="label"></div><div id="track">
                      <div id="thumb"></div></div><div id="percent"></div></div>`;
                    document.documentElement.appendChild(host);
                  }
                  const shadow = host.shadowRoot;
                  shadow.getElementById('label').textContent = String(label || 'Page').slice(0,18);
                  shadow.getElementById('percent').textContent = `${Math.round(percent)}%`;
                  shadow.getElementById('thumb').style.top =
                    `${Math.round((percent / 100) * 134)}px`;
                }
                """,
                [self._SCROLL_HUD_ID, label, position, maximum],
            )

    def _move_virtual_cursor_immediate(self, x: float, y: float) -> None:
        self.page.evaluate(
            r"""
            ([x, y, hostId]) => {
              const host = document.getElementById(hostId);
              if (!host) return;
              host.style.transition = 'none';
              host.style.transform =
                `translate3d(${Math.round(x - 29)}px, ${Math.round(y - 5)}px, 0)`;
            }
            """,
            [round(x), round(y), self._CURSOR_HOST_ID],
        )
        self._virtual_cursor_state = (x, y)

    def _move_mouse(self, x: float, y: float, action: str = "move") -> None:
        if getattr(self.settings, "cursor_mode", "virtual") != "virtual":
            super()._move_mouse(x, y, action)
            return
        self._bring_to_front()
        start_x, start_y = self._mouse_css
        self._show_virtual_cursor(start_x, start_y, "move")
        steps = max(3, min(24, round(math.hypot(x - start_x, y - start_y) / 45)))
        for index in range(1, steps + 1):
            progress = index / steps
            eased = 1.0 - (1.0 - progress) ** 3
            current_x = start_x + (x - start_x) * eased
            current_y = start_y + (y - start_y) * eased
            self.page.mouse.move(current_x, current_y)
            self._move_virtual_cursor_immediate(current_x, current_y)
            self.page.wait_for_timeout(9)
        self._show_virtual_cursor(x, y, action)
        self._mouse_css = (x, y)

    def capture(self, screenshot_path=None) -> BrowserSnapshot:
        self._update_scroll_hud()
        return super().capture(screenshot_path)

    def scroll_state(self, amount: int, ref: BrowserElementRef | None = None):
        summary, state = super().scroll_state(amount, ref)
        self._update_scroll_hud(
            str(state.get("scroll_target") or "Page"),
            int(state.get("after") or 0),
            int(state.get("maximum") or 0),
        )
        return summary, state

    def diagnostics(self, clear: bool = False) -> dict[str, object]:
        data = super().diagnostics(clear=clear)
        if not self.active:
            return data
        with suppress(Exception):
            data["semantic_page"] = self.semantic_page_state()
        aria = self._aria_snapshot()
        if aria:
            data["aria_snapshot"] = aria
        data["element_reference_policy"] = {
            "model_handles": "stable semantic E#### references",
            "execution": "live id/name/captured-selector/label/role/text resolution",
            "coordinate_fallback": "last resort only",
        }
        return data


__all__ = ["BrowserController", "SemanticBrowserElementRef"]
