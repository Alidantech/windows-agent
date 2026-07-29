---
name: core
description: Stable Windows monitor and window control strategy.
triggers: [windows, desktop, computer, screen, click, open, monitor]
---
Treat the target as a lease, not as whatever currently has foreground focus. Pixels and actions must have the same lease identity. For `monitor:N`, first discover an intended app, then bind its exact HWND or isolated browser to that monitor. Never follow the user into another window.

Prefer semantic controls in this order:
1. isolated browser actions for websites;
2. UI Automation invoke/set-value for Windows controls;
3. direct application tools and shortcuts;
4. physical cursor/keyboard only when policy permits.

The terminal running Windows Agent is protected. Never type or click into it unless the user's task explicitly targets that terminal.
