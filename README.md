# Gemini Windows Agent

**Version 0.2.0** — protected controller window, direct URL opening, robust browser discovery, visible observation status, and clean interactive-console shutdown.

A supervised Windows desktop automation project built for real use and debugging. It replaces a fragile screenshot/click loop with a structured agent that can:

- accept one task or run an interactive task console;
- save every screenshot, action overlay, model response, and execution result;
- target one active window, one monitor, a named window, or the entire desktop;
- inspect Windows UI Automation controls and click labeled elements;
- open approved Windows applications using aliases and discover common browser install paths;
- open websites directly with a safe `open_url` tool;
- use semantic keyboard actions before guessing pixels;
- detect repeated actions and stop endless loops;
- ask the user for missing information or recovery guidance;
- verify visible completion before declaring success;
- keep API keys out of logs and source control.

This is a **supervised automation tool**, not a safe autonomous administrator. Use it on reversible tasks, keep the emergency stop available, and do not use it for passwords, payments, critical decisions, or destructive system changes.

## What was happening in the interactive-console failure

`agent-os chat` runs inside Windows Terminal. Asking it to use `active-window` while the task prompt had focus meant the first screenshot could be the Agent OS terminal itself. The model then pasted application text into its own `Task:` prompt, and Enter submitted that pasted text as another task. This was foreground automation against the wrong target—not background work.

Version 0.2.0 protects the controller terminal. When it owns the foreground and the task is not explicitly a terminal task, `active-window` temporarily captures the whole desktop so the model can activate the intended app. Typing, clicking, scrolling, and submission into the controller are locally blocked.

## Why your first script got stuck

The original loop only knew `click`, `type`, and `done`. For “Open the Start menu,” it repeatedly guessed a taskbar coordinate. A click can also toggle the Start menu closed on the next turn. This project supplies a Windows skill that tells the agent to use the semantic Windows key instead, verifies the result, and blocks repeated identical actions.

## 1. Extract and enter the project

Git Bash:

```bash
unzip gemini-windows-agent.zip
cd gemini-windows-agent
```

## 2. Create an isolated environment

This avoids changing ChatGPTX's pinned Pillow and python-dotenv packages.

Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate
```

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 3. Install

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

For development tools:

```bash
python -m pip install -e ".[dev]"
```

## 4. Configure Gemini

Copy the environment template:

```bash
cp .env.example .env
```

Edit `.env` and set a newly rotated key:

```env
GEMINI_API_KEY=YOUR_NEW_KEY
GEMINI_MODEL=gemini-3.6-flash
```

Never reuse the key that appeared in your earlier terminal output.

## 5. Check the machine

```bash
agent-os doctor
```

List monitors and visible windows:

```bash
agent-os screens
```

Capture exactly what the agent sees:

```bash
agent-os capture --target active-window --output debug-active-window.png
```

Capture one monitor:

```bash
agent-os capture --target monitor:1 --output debug-monitor-1.png
```

Capture a named window:

```bash
agent-os capture --target "window:Notepad" --output debug-notepad.png
```

Export the screenshot plus machine-readable monitor, window, and UI-control metadata:

```bash
agent-os inspect --target active-window --output screen-inspection.json
```

## 6. Run the first task

```bash
agent-os run "Open the Windows Start menu" --target active-window
```

The expected first action is `press_key` with `win`, not a pixel click.

## Interactive task console

```bash
agent-os chat --target active-window
```

Then enter tasks such as:

```text
Open Notepad and type Hello from Agent OS
Open Calculator and calculate 125 * 8
Visit chatgpt.com in Chrome
Activate the browser window containing GitHub
```

Type `EXIT` to close the console.

## Target selection

| Target | Meaning |
|---|---|
| `active-window` | Capture only the current foreground window. Best default. |
| `active-monitor` | Capture the monitor containing the foreground window. |
| `monitor:1` | Capture one specific monitor. |
| `window:Notepad` | Capture the first visible title matching `Notepad` as a case-insensitive regex. |
| `desktop` | Capture the full virtual desktop across all monitors. Use sparingly. |

When the task opens or activates another app, `active-window` automatically follows the newly focused window on the next step. When the Agent OS terminal itself is active, the agent prints a controller-protection message and temporarily observes the desktop to locate the real destination.

For a known app, an explicit target remains the most deterministic option:

```bash
agent-os run "Send this message: reporting from Agent OS" --target "window:ChatGPT"
```

## Screenshots and logs

Every task creates:

```text
runs/<timestamp-task>/
├── manifest.json
├── events.jsonl
├── agent.log
└── screens/
    ├── step-001-before.png
    ├── step-001-action.png
    ├── step-002-before.png
    └── ...
```

- `before.png` is the clean screenshot sent to Gemini, before resizing.
- `action.png` overlays the selected click or element center for debugging.
- `events.jsonl` contains observations, typed model responses, action results, verifier decisions, user guidance, and stuck events.
- API keys and fields whose names resemble secrets are redacted.

List recent runs:

```bash
agent-os logs
```

Read one human-readable log:

```bash
agent-os show-log RUN_ID
```

## Dry-run mode

Plan, save, and log actions without controlling the computer:

```bash
agent-os run "Open Notepad" --dry-run
```

## Allowed applications

The agent can only launch aliases in `config/apps.yml` by default. Add or remove aliases there. This is intentionally safer than exposing an arbitrary shell command tool. Browser aliases include candidate installation paths because Chrome, Edge, and Brave are frequently installed without being added to `PATH`.

```yaml
notepad:
  command: ["notepad.exe"]
settings:
  uri: "ms-settings:"
```

Show current aliases:

```bash
agent-os apps
```

## Skills and prompts

Editable system behavior lives outside Python:

```text
prompts/system.md
prompts/verifier.md
skills/*.md
```

Skills use small YAML front matter with task triggers. The loader selects core/safety skills and the most relevant task-specific skills. For example, `skills/start_menu.md` explicitly tells the model to press the Windows key.

## Safety and emergency stop

- Move the mouse pointer into the top-left corner to trigger PyAutoGUI fail-safe.
- Press `Ctrl+C` to stop the current run.
- Repeated identical actions are blocked after the configured limit.
- Certain hotkeys require terminal confirmation; some are blocked.
- No arbitrary PowerShell, Command Prompt, Python, or shell-execution tool is exposed to the model.
- App launching is allow-listed.
- Completion is checked by a separate visual verifier call.

Read `docs/SAFETY.md` before expanding the tool set.

## Configuration

Configuration is read from `.env` using the `AGENT_OS_` prefix. Important options:

```env
AGENT_OS_TARGET=active-window
AGENT_OS_MAX_STEPS=30
AGENT_OS_REPEAT_LIMIT=3
AGENT_OS_SAVE_SCREENSHOTS=true
AGENT_OS_USE_UIA=true
AGENT_OS_CONFIRM_RISKY=true
AGENT_OS_VERIFY_DONE=true
AGENT_OS_ALLOW_UNLISTED_APPS=false
```

## Tests

```bash
pytest
```

Static checks:

```bash
ruff check .
python -m compileall src tests
```

## Known limitations

- Windows only. The code intentionally fails early on other operating systems.
- Some elevated/admin windows reject automation from a non-elevated process.
- UI Automation metadata quality differs between Win32, Chromium, Electron, Flutter, games, and custom-rendered apps.
- Visual models can still choose an incorrect action. Supervision and logs remain necessary.
- Screen scaling, remote desktop sessions, animations, popups, and rapidly changing interfaces can reduce reliability.
- `active-window` may capture a temporary popup after an action. Use `active-monitor` when surrounding context is necessary.

See `docs/TROUBLESHOOTING.md` and `docs/RESEARCH.md` for implementation details and source decisions.

## Visible execution and controller protection

At every step the console now prints `Seeing:` followed by the exact window or desktop region sent to the model and the saved screenshot path. Actions are not executed by a hidden background service:

- mouse actions use foreground desktop input;
- typing pastes into the foreground destination;
- `activate_window` brings a visible window forward;
- `open_url` launches or activates a browser;
- UI Automation clicking uses visible input rather than silent background mutation.

After a run, inspect the evidence under `runs/<run-id>/screens/` and `events.jsonl`.

## Upgrade an existing 0.1.0 checkout

Extract the 0.2.0 archive over the existing project directory. The archive does not contain `.env` or `runs/`, so your API key and run history are preserved. Then reinstall editable metadata:

```bash
cd ~/Projects/gemini-windows-agent
source .venv/Scripts/activate
python -m pip install -e .
```
