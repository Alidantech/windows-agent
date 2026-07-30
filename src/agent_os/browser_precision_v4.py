from __future__ import annotations

from pathlib import Path

from agent_os.browser import BrowserSnapshot
from agent_os.browser_precision_v3 import BrowserController as BaseBrowserController


class BrowserController(BaseBrowserController):
    """Render the virtual pointer inside the controlled page, never in a Tk window."""

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
                    font-family: "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif;
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
              const target = `translate3d(${Math.round(x - 29)}px, ${Math.round(y - 5)}px, 0)`;
              if (host.dataset.ready === '1') {
                host.style.transition = 'transform 145ms cubic-bezier(.2,.8,.2,1)';
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
        try:
            self.page.evaluate(
                r"""
                hostId => {
                  const host = document.getElementById(hostId);
                  if (host) host.style.display = 'none';
                }
                """,
                self._CURSOR_HOST_ID,
            )
        except Exception:
            pass

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
                try:
                    self._show_virtual_cursor(state[0], state[1], "restore")
                except Exception:
                    pass

    def close(self, force: bool = False) -> None:
        self._virtual_cursor_state = None
        super().close(force=force)


__all__ = ["BrowserController"]
