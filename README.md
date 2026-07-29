# Agent OS v0.3

A supervised Gemini-powered Windows automation agent built around one safety invariant:

> **The pixels the model sees and the target that receives the action must belong to the same control lease.**

Agent OS v0.3 supports dedicated-monitor assignment, exact window leases, independent browser automation through Playwright, Windows UI Automation, a click-through neon monitor overlay, saved screenshots, structured logs, deterministic website smoke tests, and physical-input conflict policies.

## What changed in v0.3

The earlier monitor mode captured a monitor but still followed whichever application became active. That allowed screenshots and input destinations to diverge. v0.3 replaces that behavior with a stable lease:

- `monitor:3` assigns the workspace to monitor 3.
- The first launched/selected app is discovered and its exact HWND is bound to that monitor.
- Later screenshots capture that same HWND with `PrintWindow` when available.
- UI elements, clicks, text, logs, and completion checks carry the same lease ID and capture token.
- If independent capture is unavailable and another window owns focus, strict mode stops rather than sending unrelated pixels.
- Website tasks default to an isolated Playwright browser with virtual page mouse and keyboard input.

## Interaction backends

### Isolated browser — recommended for websites

Playwright runs a visible persistent browser on the assigned monitor. Its mouse and keyboard are page-level virtual inputs, so they do not move your Windows cursor or type through your physical keyboard.

Supported browser actions include:

- open a URL;
- click coordinates or DOM elements;
- fill text fields;
- press keys and shortcuts;
- scroll;
- collect console and failed-request diagnostics;
- deterministically smoke-test every unique same-origin link.

### Windows UI Automation — recommended for desktop apps

For normal Windows applications, Agent OS tries semantic UI Automation first:

- invoke buttons and links;
- set values in supported text controls;
- inspect labeled controls;
- bind an exact HWND;
- move the controlled window to the assigned monitor.

### Shared physical fallback

Some applications expose neither browser automation nor semantic UI Automation. Physical fallback can use the real Windows cursor/keyboard, but it is governed by policy:

- `deny`: never use shared physical input;
- `ask`: request approval once per run;
- `allow`: permit physical fallback.

`cooperative` conflict mode refuses to steal focus. `exclusive` mode may focus the leased window when physical input is necessary. Coordinate clicks restore the user's pointer after the action when possible.

## Visual overlay

When a monitor is assigned, Agent OS draws a click-through overlay:

- neon border around the controlled monitor;
- current lease and status;
- vibrant virtual AI cursor/crosshair;
- state colors for ready, working, waiting, question, and error.

The overlay attempts to exclude itself from screen capture so the model does not confuse it with the application UI.

## Requirements

- Windows 10 or Windows 11
- Python 3.11–3.13
- A Gemini API key
- An isolated Python virtual environment
- Playwright Chromium for independent browser control

## Installation in Git Bash

```bash
cd ~/Projects/gemini-windows-agent
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
cp .env.example .env
```

Add your Gemini API key to `.env`:

```env
GEMINI_API_KEY=YOUR_NEW_KEY
GEMINI_MODEL=gemini-3.5-flash-lite
```

Validate the installation:

```bash
agent-os doctor
```

## Recommended dedicated-monitor configuration

```env
AGENT_OS_TARGET=monitor:3
AGENT_OS_CONTROL_MODE=auto
AGENT_OS_BROWSER_BACKEND=isolated
AGENT_OS_CONFLICT_POLICY=cooperative
AGENT_OS_PHYSICAL_INPUT_POLICY=deny
AGENT_OS_STRICT_CAPTURE_ALIGNMENT=true
AGENT_OS_MOVE_BOUND_WINDOW_TO_MONITOR=true
AGENT_OS_OVERLAY_ENABLED=true
```

This is the safest configuration while you continue using another monitor.

## Discover monitors and exact windows

```bash
agent-os screens
```

The command prints:

- monitor indexes and geometry;
- each visible window's monitor;
- process name;
- exact HWND;
- exact target such as `hwnd:428772`.

Preview a lease without acting:

```bash
agent-os lease-preview --target monitor:3
agent-os lease-preview --target hwnd:428772
agent-os lease-preview --target process:chrome
agent-os lease-preview --target "window:DeFy Tickets"
```

Window title matching is fuzzy. Browser suffixes such as Chrome, Brave, and Edge are ignored when the meaningful page title matches. For guaranteed targeting, use `hwnd:NUMBER`.

## Run a website task independently

```bash
agent-os run \
  "Open defytickets.com and smoke test every same-origin link" \
  --target monitor:3 \
  --control-mode browser \
  --physical-input deny
```

The expected high-level flow is:

1. `open_url` starts the isolated browser on monitor 3.
2. The lease binds to the browser session.
3. `smoke_test_site` inventories and tests links without manually clicking each one.
4. A report is written under the run folder.

Example report location:

```text
runs/<run-id>/browser-smoke/smoke-report.json
```

Each result contains the requested URL, final URL, HTTP status, title, page errors, failed requests, duration, pass/fail status, and screenshot path.

## Interactive mode

Use `chat` when you want the same isolated browser profile/session to stay alive across several tasks:

```bash
agent-os chat \
  --target monitor:3 \
  --control-mode auto \
  --physical-input deny
```

Example tasks:

```text
Open chatgpt.com
Open defytickets.com and smoke test every same-origin link
In the current page, identify visible form fields
EXIT
```

## Desktop application modes

Safest semantic-only mode:

```bash
agent-os run "Open Calculator and calculate 125 times 8" \
  --target monitor:3 \
  --control-mode desktop \
  --conflict-policy cooperative \
  --physical-input deny
```

Allow supervised physical fallback:

```bash
agent-os run "Open a legacy app and complete the visible form" \
  --target monitor:3 \
  --control-mode desktop \
  --conflict-policy exclusive \
  --physical-input ask
```

## Inspect exactly what the desktop backend sees

```bash
agent-os inspect --target hwnd:428772 --output inspection.json
```

The output includes:

- target and HWND;
- capture source;
- target identity;
- capture token;
- monitor layout;
- visible windows;
- UI Automation elements;
- screenshot path.

A target captured through `print-window` can remain visually stable even when you focus another app. If Windows or the application does not support independent capture, strict alignment stops instead of silently capturing the foreground window.

## Logs and evidence

Each run creates:

```text
runs/<run-id>/
├── manifest.json
├── events.jsonl
├── agent.log
├── screens/
│   ├── step-001-before.png
│   ├── step-001-action.png
│   └── ...
└── browser-smoke/
    ├── smoke-report.json
    └── *.png
```

Important logged fields include:

- lease ID and generation;
- assigned monitor;
- controlled HWND/browser identity;
- capture source and capture token;
- raw Gemini decisions;
- tool input backend (`browser-virtual`, `uia`, or `physical`);
- completion-verifier evidence;
- browser console and request failures.

## Key commands

```bash
agent-os doctor
agent-os browser-install
agent-os screens
agent-os lease-preview --target monitor:3
agent-os capture --target hwnd:NUMBER --output capture.png
agent-os inspect --target hwnd:NUMBER --output inspection.json
agent-os run "TASK" --target monitor:3
agent-os chat --target monitor:3
agent-os logs
agent-os show-log RUN_ID
```

## Safety and limitations

- A normal Windows desktop session has one system cursor and one foreground keyboard focus.
- Agent OS cannot create a second native Windows cursor for arbitrary applications.
- The neon cursor is a visible overlay; browser virtual input and UI Automation are the mechanisms that provide practical independence.
- Playwright controls only its isolated browser session, not an already-open personal Chrome window.
- Some DRM, GPU-rendered, elevated, or protected windows may not support `PrintWindow` or UI Automation.
- Physical fallback can conflict with user activity; keep it denied unless needed.
- The top-left PyAutoGUI fail-safe and `Ctrl+C` remain emergency stops.
- Never place passwords, API keys, payment details, or other secrets in an agent task.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
ruff check src tests
python -m compileall -q src tests
```

See `docs/ARCHITECTURE.md`, `docs/SAFETY.md`, and `docs/TROUBLESHOOTING.md` for implementation details.
