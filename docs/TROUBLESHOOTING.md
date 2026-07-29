# Troubleshooting

## The agent repeats the same action

The run should emit `stuck_detected` after the repeat limit. Inspect:

```text
runs/<run>/screens/*-before.png
runs/<run>/screens/*-action.png
runs/<run>/events.jsonl
```

Use `agent-os capture` to verify the chosen target. Switch from `active-window` to `active-monitor` when a popup or taskbar is outside the active window.

## It clicks the wrong place

This project uses normalized 0..1000 target coordinates, so image resizing does not require separate coordinate scaling. Wrong clicks usually mean the model misidentified the control or the target changed after capture. Prefer `click_element` by enabling UIA and targeting one window.

## Start menu opens and closes

Use the included start-menu skill. The first action should be:

```json
{"action":"press_key","key":"win"}
```

If the model clicks the taskbar instead, confirm `skills/start_menu.md` exists and the task contains “Start menu.”

## API errors

Run:

```bash
agent-os doctor
```

Confirm `.env` contains only the key value and model name. The SDK constructs the endpoint; do not concatenate an API key into a URL.

## `ModuleNotFoundError`

Activate this project's virtual environment before running commands:

```bash
source .venv/Scripts/activate
```

Then reinstall:

```bash
python -m pip install -e .
```

## ChatGPTX dependency conflict

Do not install this project globally. Its isolated venv pins Pillow 11.1.0 and python-dotenv 1.0.1, matching the conflict shown by ChatGPTX.

## Windows scale/DPI problems

First inspect the actual capture:

```bash
agent-os capture --target active-monitor --output dpi-debug.png
```

Prefer UI Automation element clicking. Keep all monitors on stable scaling while testing. Restart the agent after changing Windows display scaling.

## Elevated window cannot be controlled

Windows can prevent a normal process from controlling an elevated process. Do not automatically run the agent as Administrator. Use a non-elevated target app or manually complete the administrative step.

## UI Automation returns no elements

Some apps draw custom pixels and expose little accessibility information. Use `active-monitor` and visual actions, or add a narrow app-specific skill. Do not increase `AGENT_OS_MAX_UI_ELEMENTS` excessively because large accessibility trees increase prompt size and latency.
