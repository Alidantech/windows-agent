# Safety model

## Default recommendation

Use an isolated browser, cooperative conflict policy, and denied physical input:

```env
WINDOWS_AGENT_CONTROL_MODE=auto
WINDOWS_AGENT_BROWSER_BACKEND=isolated
WINDOWS_AGENT_CONFLICT_POLICY=cooperative
WINDOWS_AGENT_PHYSICAL_INPUT_POLICY=deny
```

## Boundaries

- The controller terminal is protected unless the task explicitly targets a terminal.
- A desktop action is blocked when screenshot HWND and lease HWND differ.
- Coordinates outside the assigned monitor are rejected.
- Cooperative mode does not steal foreground focus for physical input.
- Cursor-motion detection pauses physical fallback when the user is moving the pointer.
- Risky shortcuts, non-HTTP URLs, secret-like typing, and destructive actions are blocked or confirmed.
- Browser automation occurs only inside the isolated Playwright profile.

## Emergency stops

- Press `Ctrl+C` in the controller terminal.
- Move the system pointer to the top-left corner to trigger PyAutoGUI's fail-safe during physical fallback.
