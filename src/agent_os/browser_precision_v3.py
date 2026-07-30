from __future__ import annotations

import json

from agent_os.browser import BrowserElementRef
from agent_os.browser_precision_v2 import BrowserController as BaseBrowserController
from agent_os.models import UIElement
from agent_os.system_cursor import move_to as move_system_cursor


class BrowserController(BaseBrowserController):
    """Form-aware browser controller with selectable cursor presentation."""

    def _snapshot_elements(self, image_width: int, image_height: int):
        elements, wrappers = super()._snapshot_elements(image_width, image_height)
        metadata = self.page.evaluate(
            r"""
            () => {
              const output = {};
              for (const el of document.querySelectorAll('[data-windows-agent-id]')) {
                const id = el.getAttribute('data-windows-agent-id');
                if (!id) continue;
                const tag = el.tagName.toLowerCase();
                const type = tag === 'input' ? (el.type || 'text').toLowerCase() :
                  (tag === 'button' ? (el.type || 'submit').toLowerCase() : null);
                const isPassword = type === 'password';
                const rawValue = ('value' in el && typeof el.value === 'string') ? el.value :
                  (el.isContentEditable ? (el.innerText || '') : '');
                const form = el.form || el.closest('form');
                let valid = null;
                let validationMessage = null;
                try {
                  valid = typeof el.checkValidity === 'function' ? el.checkValidity() : null;
                  validationMessage = valid === false ? (el.validationMessage || null) : null;
                } catch (_) {}
                const semanticName = (el.getAttribute('aria-label') ||
                  (el.innerText || el.textContent || '') ||
                  el.getAttribute('name') || '').replace(/\s+/g, ' ').trim();
                const submitLike = /\b(?:submit|save|continue|next|finish|publish|create|confirm)\b/i
                  .test(semanticName);
                output[id] = {
                  hasValue: Boolean(rawValue),
                  valueLength: rawValue.length,
                  valuePreview: isPassword ? null : rawValue.slice(0, 120),
                  valid,
                  validationMessage,
                  formId: form ? (form.id || form.getAttribute('name') || 'form') : null,
                  isSubmit: (tag === 'button' && type === 'submit') ||
                    (tag === 'input' && ['submit', 'image'].includes(type)) ||
                    ((tag === 'button' || el.getAttribute('role') === 'button') && submitLike),
                  ariaExpanded: el.hasAttribute('aria-expanded') ?
                    el.getAttribute('aria-expanded') === 'true' : null,
                };
              }
              return output;
            }
            """
        )
        for element in elements:
            item = (metadata or {}).get(element.element_id) or {}
            element.has_value = item.get("hasValue")
            element.value_length = item.get("valueLength")
            element.value_preview = item.get("valuePreview")
            element.valid = item.get("valid")
            element.validation_message = item.get("validationMessage")
            element.form_id = item.get("formId")
            element.is_submit = bool(item.get("isSubmit"))
            element.aria_expanded = item.get("ariaExpanded")
        return elements, wrappers

    def form_state(self) -> dict[str, object]:
        return self.page.evaluate(
            r"""
            () => {
              const fieldName = (el) => {
                const labels = el.labels ? Array.from(el.labels)
                  .map(label => label.innerText || label.textContent || '').join(' ') : '';
                const aria = el.getAttribute('aria-label') || '';
                const placeholder = el.getAttribute('placeholder') || '';
                return (aria || labels || placeholder || el.getAttribute('name') ||
                  el.id || el.tagName.toLowerCase()).replace(/\s+/g, ' ').trim().slice(0, 180);
              };
              const forms = Array.from(document.forms).map((form, index) => {
                const invalid = [];
                const missing = [];
                for (const el of Array.from(form.elements || [])) {
                  if (!el || typeof el !== 'object') continue;
                  const name = fieldName(el);
                  let isValid = true;
                  try {
                    isValid = typeof el.checkValidity === 'function' ? el.checkValidity() : true;
                  } catch (_) {}
                  if (!isValid) {
                    invalid.push({
                      name,
                      message: (el.validationMessage || '').slice(0, 220),
                    });
                  }
                  const required = Boolean(el.required) || el.getAttribute?.('aria-required') === 'true';
                  if (!required) continue;
                  const type = (el.type || '').toLowerCase();
                  const absent = ['checkbox', 'radio'].includes(type) ? !el.checked :
                    !String(el.value || '').trim();
                  if (absent) missing.push(name);
                }
                return {
                  id: form.id || form.getAttribute('name') || `form-${index + 1}`,
                  valid: typeof form.checkValidity === 'function' ? form.checkValidity() : invalid.length === 0,
                  invalidFields: invalid,
                  missingRequired: missing,
                };
              });
              const alerts = Array.from(document.querySelectorAll(
                '[role="alert"], [aria-live="assertive"], [data-error], .error, .field-error'
              )).filter(el => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' &&
                  style.display !== 'none';
              }).map(el => (el.innerText || el.textContent || '').replace(/\s+/g, ' ')
                .trim().slice(0, 260)).filter(Boolean).slice(0, 20);
              const active = document.activeElement;
              return {
                url: location.href,
                title: document.title,
                forms,
                alerts,
                activeElement: active ? {
                  id: active.getAttribute('data-windows-agent-id') || active.id || null,
                  name: fieldName(active),
                } : null,
              };
            }
            """
        )

    def diagnostics(self, clear: bool = False) -> dict[str, object]:
        data = super().diagnostics(clear=clear)
        if self.active:
            try:
                data["form_state"] = self.form_state()
            except Exception as exc:
                data["form_state_error"] = str(exc)[:300]
        return data

    def _emit_pointer(self, x: float, y: float, action: str) -> None:
        viewport = self.viewport_screen_rect()
        screen_x = viewport.left + round(x)
        screen_y = viewport.top + round(y)
        mode = getattr(self.settings, "cursor_mode", "virtual")
        if mode == "off":
            return
        if mode == "system":
            if self.settings.physical_input_policy == "deny":
                raise RuntimeError(
                    "System cursor mode requires physical input permission. "
                    "Use `/set physical allow` or switch to `/set cursor virtual`."
                )
            move_system_cursor(screen_x, screen_y, duration_ms=150)
            return
        if self._pointer_sink is not None:
            self._pointer_sink(screen_x, screen_y, action)

    @staticmethod
    def _state_signature(state: dict[str, object]) -> str:
        meaningful = {
            "url": state.get("url"),
            "title": state.get("title"),
            "forms": state.get("forms"),
            "alerts": state.get("alerts"),
        }
        return json.dumps(meaningful, sort_keys=True, ensure_ascii=False, default=str)

    def click_element_state(
        self,
        ref: BrowserElementRef,
        element: UIElement,
    ) -> tuple[str, dict[str, object]]:
        before = self.form_state()
        before_signature = self._state_signature(before)
        summary = super().click_element(ref)
        self.page.wait_for_timeout(420)
        after = self.form_state()
        changed = self._state_signature(after) != before_signature
        invalid_fields = []
        missing_required = []
        for form in after.get("forms", []):
            if not isinstance(form, dict):
                continue
            invalid_fields.extend(form.get("invalidFields") or [])
            missing_required.extend(form.get("missingRequired") or [])
        details = {
            "changed": changed,
            "is_submit": bool(element.is_submit),
            "url_before": before.get("url"),
            "url_after": after.get("url"),
            "invalid_fields": invalid_fields,
            "missing_required": missing_required,
            "alerts": after.get("alerts") or [],
            "form_state": after,
        }
        return summary, details

    def fill_element_state(
        self,
        ref: BrowserElementRef,
        element: UIElement,
        text: str,
    ) -> tuple[str, dict[str, object]]:
        summary = super().fill_element(ref, text)
        self.page.wait_for_timeout(100)
        state = self._locator(ref).evaluate(
            r"""
            el => {
              const raw = ('value' in el && typeof el.value === 'string') ? el.value :
                (el.isContentEditable ? (el.innerText || '') : '');
              let valid = null;
              let message = null;
              try {
                valid = typeof el.checkValidity === 'function' ? el.checkValidity() : null;
                message = valid === false ? (el.validationMessage || null) : null;
              } catch (_) {}
              return {valueLength: raw.length, hasValue: Boolean(raw), valid, message};
            }
            """
        )
        details = {
            "element_id": element.element_id,
            "value_length": state.get("valueLength"),
            "has_value": state.get("hasValue"),
            "valid": state.get("valid"),
            "validation_message": state.get("message"),
        }
        return summary, details


__all__ = ["BrowserController"]
