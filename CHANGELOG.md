# Changelog

## 0.5.0

- Rebranded the product and distribution from Gemini Windows Agent / Agent OS to Windows Agent.
- Added the primary `windows-agent` CLI while retaining `agent-os` as a compatibility alias.
- Added a provider protocol and lazy provider registry.
- Moved Gemini behind a provider adapter without changing its existing behavior.
- Added optional OpenAI Responses API and Mistral vision/structured-output adapters.
- Added `WINDOWS_AGENT_PROVIDER` and `WINDOWS_AGENT_MODEL` configuration.
- Added backward-compatible promotion of legacy `AGENT_OS_*` environment variables.
- Added provider diagnostics and the `windows-agent providers` command.
- Changed the default runtime state directory to `.windows-agent/`.

## 0.3.0

- Replaced loose monitor observation with a stable monitor/window/browser control lease.
- Added exact `hwnd:NUMBER` and `process:NAME` targets plus fuzzy cross-browser title matching.
- Added strict screenshot/action alignment and capture tokens.
- Added Win32 `PrintWindow` capture for bound windows.
- Added isolated Playwright browser control with virtual mouse and keyboard.
- Added deterministic same-origin site smoke testing and JSON evidence reports.
- Added monitor border, status banner, and vibrant virtual agent cursor overlay.
- Added cooperative/exclusive conflict modes and deny/ask/allow physical-input policies.
- Added UI Automation-first desktop clicking and text entry.
- Added browser installation, lease preview, richer doctor, and exact target diagnostics.
- Reused the same agent/browser instance across interactive chat tasks.
- Prevented repeated lease-bound log spam and strengthened completion verification.

## 0.2.0

- Protected the Windows Agent terminal from typing into itself.
- Added direct URL opening and fuzzy window targeting.
- Added saved screenshots, logs, and completion verification.
