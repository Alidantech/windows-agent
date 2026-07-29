---
name: core
description: Core Windows interaction strategy.
triggers: [windows, desktop, computer, screen, click, open]
---
Prefer Windows semantic controls in this order:

1. `launch_app` for known app aliases.
2. `activate_window` for a visible existing app.
3. `press_key` or `hotkey` for standard Windows navigation.
4. `click_element` when UI Automation provides a matching labeled control.
5. Normalized coordinate clicks only when no semantic method exists.

After every action, inspect the new screenshot. Do not assume the interface changed.
