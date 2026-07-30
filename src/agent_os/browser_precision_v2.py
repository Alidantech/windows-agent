from __future__ import annotations

from agent_os.browser_precision import BrowserController as BaseBrowserController


class BrowserController(BaseBrowserController):
    """Use wheel input at the focused control and measure the actual scroll container."""

    def _scroll_anchor(self) -> tuple[float, float]:
        point = self.page.evaluate(
            """() => {
              const el = document.activeElement;
              if (el && el !== document.body && el !== document.documentElement) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 1 && rect.height > 1 && rect.bottom > 0 && rect.right > 0 &&
                    rect.top < innerHeight && rect.left < innerWidth) {
                  return {
                    x: Math.min(innerWidth - 1, Math.max(0, rect.left + rect.width / 2)),
                    y: Math.min(innerHeight - 1, Math.max(0, rect.top + rect.height / 2))
                  };
                }
              }
              return {x: innerWidth / 2, y: innerHeight / 2};
            }"""
        )
        return float(point["x"]), float(point["y"])

    def _scroll_state(self, x: float, y: float) -> dict[str, object]:
        return self.page.evaluate(
            r"""
            ([x, y]) => {
              let el = document.elementFromPoint(x, y);
              while (el && el !== document.documentElement) {
                const style = getComputedStyle(el);
                const scrollable = /(auto|scroll|overlay)/.test(style.overflowY) &&
                  el.scrollHeight > el.clientHeight + 1;
                if (scrollable) {
                  return {
                    kind: 'element',
                    name: el.getAttribute('aria-label') || el.id || el.tagName.toLowerCase(),
                    top: el.scrollTop
                  };
                }
                el = el.parentElement;
              }
              return {kind: 'window', name: 'window', top: window.scrollY};
            }
            """,
            [x, y],
        )

    def scroll(self, amount: int) -> str:
        x, y = self._scroll_anchor()
        self._move_mouse(x, y, "scroll")
        before = self._scroll_state(x, y)
        delta = amount * self.settings.browser_scroll_pixels
        self.page.mouse.wheel(0, delta)
        self.page.wait_for_timeout(180)
        after = self._scroll_state(x, y)
        moved = round(float(after.get("top") or 0) - float(before.get("top") or 0))
        direction = "down" if amount > 0 else "up"
        target = str(after.get("name") or after.get("kind") or "page")
        return (
            f"Scrolled {target} {direction} with the virtual mouse wheel "
            f"({delta} CSS pixels requested, {moved} observed)."
        )


__all__ = ["BrowserController"]
