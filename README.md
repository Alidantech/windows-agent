# Windows Agent

**Version 0.5.0**

Windows Agent is a supervised Windows desktop automation project with provider-pluggable vision planning, stable monitor/window leases, independent browser input, Windows UI Automation, safe visual overlays, saved evidence, and deterministic website smoke testing.

The core safety invariant is:

> The pixels sent to the model and the target receiving the action must belong to the same control lease.

Gemini is the default provider. OpenAI and Mistral can be selected without changing the desktop-control code.

## Capabilities

- Assign a dedicated monitor, exact HWND, process, named window, active window, or full desktop.
- Bind screenshots, UI metadata and actions to one leased target.
- Run websites in an isolated Playwright browser with its own page-level mouse and keyboard.
- Use UI Automation for semantic desktop interaction before physical input.
- Deny, ask for, or allow physical mouse/keyboard fallback.
- Show a thin controlled-monitor border and vibrant virtual agent cursor.
- Save screenshots, model decisions, tool results and manifests for every run.
- Deterministically discover and smoke-test same-origin website links.
- Cancel current work with Ctrl+C and terminate owned browser processes.
- Load task-specific skills from Markdown files.

## Supported AI providers

| Provider | Status | Key | Installation |
|---|---|---|---|
| Gemini | Built in and default | `GEMINI_API_KEY` | Base installation |
| OpenAI | Optional | `OPENAI_API_KEY` | `python -m pip install -e ".[openai]"` |
| Mistral | Optional | `MISTRAL_API_KEY` | `python -m pip install -e ".[mistral]"` |

See [Provider architecture](docs/PROVIDERS.md) for adapter details and custom-provider registration.

## Requirements

- Windows 10 or Windows 11
- Python 3.11–3.13
- An API key for the selected AI provider
- Playwright Chromium for independent browser control

## Installation using Git Bash

```bash
cd ~/Projects/windows-agent
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
cp .env.example .env
```

The package installs two commands:

```text
windows-agent   Primary command
agent-os        Temporary compatibility alias
```

## Configure a provider

Gemini:

```env
WINDOWS_AGENT_PROVIDER=gemini
WINDOWS_AGENT_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=YOUR_KEY
```

OpenAI:

```bash
python -m pip install -e ".[openai]"
```

```env
WINDOWS_AGENT_PROVIDER=openai
WINDOWS_AGENT_MODEL=gpt-5-mini
OPENAI_API_KEY=YOUR_KEY
```

Mistral:

```bash
python -m pip install -e ".[mistral]"
```

```env
WINDOWS_AGENT_PROVIDER=mistral
WINDOWS_AGENT_MODEL=mistral-small-latest
MISTRAL_API_KEY=YOUR_KEY
```

`WINDOWS_AGENT_MODEL` has priority. `GEMINI_MODEL`, `OPENAI_MODEL` and `MISTRAL_MODEL` remain provider-specific fallbacks.

Existing `AGENT_OS_*` environment variables remain accepted during migration, but new configuration should use `WINDOWS_AGENT_*`.

## Validate the machine

```bash
windows-agent doctor
windows-agent providers
windows-agent screens
```

Install Playwright separately when needed:

```bash
windows-agent browser-install
```

## Dedicated-monitor browser task

```bash
windows-agent run \
  "Open defytickets.com and smoke test every unique same-origin link" \
  --target monitor:3 \
  --control-mode browser \
  --physical-input deny
```

Expected high-level flow:

```text
open_url
smoke_test_site
complete from deterministic evidence
```

The browser backend uses Playwright's virtual page mouse and keyboard, so it does not move your Windows pointer or type through your physical keyboard.

## Select a provider per run

Global provider options must appear before the command:

```bash
windows-agent --provider openai --model gpt-5-mini run \
  "Open example.com and describe the visible page" \
  --target monitor:3 \
  --physical-input deny
```

## Interactive task console

```bash
windows-agent chat \
  --target monitor:3 \
  --control-mode auto \
  --physical-input deny
```

Example tasks:

```text
Open chatgpt.com
Open defytickets.com and smoke test every same-origin link
Open Notepad on the assigned monitor and type Hello from Windows Agent
EXIT
```

## Exact target selection

```bash
windows-agent screens
```

Then target an exact HWND:

```bash
windows-agent run "Continue testing this application" --target hwnd:428772
```

Other accepted targets include:

```text
active-window
active-monitor
monitor:3
process:chrome
window:DeFy Tickets
desktop
```

## Safe default configuration

```env
WINDOWS_AGENT_TARGET=monitor:3
WINDOWS_AGENT_CONTROL_MODE=auto
WINDOWS_AGENT_BROWSER_BACKEND=isolated
WINDOWS_AGENT_CONFLICT_POLICY=cooperative
WINDOWS_AGENT_PHYSICAL_INPUT_POLICY=deny
WINDOWS_AGENT_STRICT_CAPTURE_ALIGNMENT=true
WINDOWS_AGENT_MOVE_BOUND_WINDOW_TO_MONITOR=true
WINDOWS_AGENT_OVERLAY_ENABLED=true
```

In this mode, unsupported physical interaction fails closed rather than taking your mouse or keyboard.

## Overlay test

Test the monitor border without calling an AI provider:

```bash
windows-agent overlay-test --target monitor:3 --seconds 8
```

The overlay uses thin border windows and a small status/cursor badge; it must never cover the controlled monitor with an opaque surface.

## Evidence and logs

Every task creates:

```text
runs/<run-id>/
├── manifest.json
├── events.jsonl
├── agent.log
├── screens/
└── browser-smoke/
    ├── smoke-report.json
    └── smoke-report.html
```

Useful commands:

```bash
windows-agent logs
windows-agent show-log RUN_ID
windows-agent inspect --target monitor:3 --output inspection.json
```

## Safety

- Move the pointer to the top-left corner for the PyAutoGUI fail-safe.
- Press Ctrl+C to cancel the current task.
- Use `WINDOWS_AGENT_PHYSICAL_INPUT_POLICY=deny` while doing other work.
- Do not use the agent for passwords, payments, destructive administration, or irreversible actions.
- Browser and UI Automation backends are preferred over shared physical input.
- The tool is supervised automation, not a trustworthy autonomous administrator.

Read [Safety](docs/SAFETY.md) and [Troubleshooting](docs/TROUBLESHOOTING.md) before expanding tools.

## Development

```bash
pytest
ruff check .
python -m compileall src tests
```

Internal Python imports remain under `agent_os` in v0.5 for compatibility. The public distribution, command, documentation and runtime namespace are now Windows Agent.
