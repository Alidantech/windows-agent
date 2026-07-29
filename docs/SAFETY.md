# Safety

Windows Agent is supervised automation, not an autonomous administrator.

Recommended defaults:

```env
WINDOWS_AGENT_CONTROL_MODE=auto
WINDOWS_AGENT_BROWSER_BACKEND=isolated
WINDOWS_AGENT_CONFLICT_POLICY=cooperative
WINDOWS_AGENT_PHYSICAL_INPUT_POLICY=deny
WINDOWS_AGENT_STRICT_CAPTURE_ALIGNMENT=true
WINDOWS_AGENT_OVERLAY_ENABLED=true
```

Inside the persistent console:

```text
/set control auto
/set physical deny
/set overlay on
```

Browser automation uses Playwright's page-level virtual mouse and keyboard. Desktop automation prefers UI Automation. Shared physical input is a fallback and should remain denied unless the user deliberately enables it.

API keys are entered through `/key set PROVIDER` using a masked prompt and stored in Windows Credential Manager. They are never echoed or written to prompt history.

Ctrl+C cancels the active task without closing the console. `/exit` closes the console. Destructive actions, credentials, payments, administrator prompts and security warnings require explicit human control.
