# Architecture

## Control loop

1. Resolve a capture target: active window, active monitor, named window, monitor, or desktop.
2. Capture it using MSS and save the original PNG.
3. Collect visible windows and, for a window target, a bounded UI Automation element snapshot.
4. Select relevant Markdown skills for the task.
5. Send task context, recent tool history, UI metadata, and the resized screenshot to Gemini.
6. Parse the response into the Pydantic `AgentDecision` schema.
7. Apply local safety policy and repeated-action detection.
8. Execute one action with PyAutoGUI, UI Automation, AppLauncher, or WindowManager.
9. Save an annotated action image and structured event.
10. Repeat with a new screenshot.
11. When the planner says `done`, use a separate typed visual verification request before ending.

## Main modules

- `config.py`: environment-based settings and API key loading.
- `models.py`: typed action, screen, UI, result, and verification models.
- `capture.py`: MSS monitor/window capture, image resizing, and action overlays.
- `windows.py`: top-level window discovery, activation, and UI Automation snapshots.
- `provider.py`: Google Gen AI SDK calls with image bytes and typed JSON output.
- `prompts.py`: external prompt and skill assembly.
- `skills.py`: Markdown skill parsing and task matching.
- `tools.py`: one-action execution.
- `safety.py`: blocked and confirmation-required local actions.
- `repeat.py`: repeated identical action detector.
- `runlog.py`: redacted JSONL, text logs, manifests, and run folders.
- `agent.py`: orchestration, asking the user, recovery, and completion verification.
- `cli.py`: doctor, screen discovery, capture, run, chat, apps, and log commands.

## Coordinate model

The model returns x/y values from 0 to 1000 relative to the selected capture rectangle. The executor maps those normalized coordinates directly to the original target rectangle. This remains correct when the screenshot sent to Gemini is resized and also works with monitors positioned at negative virtual-desktop coordinates.

## Why typed planner actions instead of free-form JSON

The Gemini SDK is configured with a Pydantic response schema. Invalid action names and missing fields fail validation before any desktop action can run. This avoids treating an HTTP error or an explanatory paragraph as executable JSON.

## Why UI Automation plus pixels

Pixels provide universal visual context. UI Automation can provide labeled controls, control types, automation IDs, bounds, enabled state, and direct element clicking. The agent prefers those semantic elements but falls back to visual coordinates when an app exposes no useful accessibility tree.
