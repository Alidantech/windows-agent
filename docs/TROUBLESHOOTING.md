# Troubleshooting

## `uv` is not found

Install uv with WinGet:

```powershell
winget install --id=astral-sh.uv -e
```

Or use the official installer:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen the terminal, then run `uv --version`.

## Dependency or environment problems

Do not activate or modify `.venv` manually. Resynchronize exactly from project metadata:

```bash
uv sync
```

For a completely fresh local environment:

```bash
rm -rf .venv
uv sync
```

After `uv.lock` is committed, validate it with:

```bash
uv lock --check
uv sync --locked
```

## The assigned monitor becomes black

Windows Agent v0.6 never creates a monitor-sized overlay. The overlay is a separate process containing only four thin border strips and two small badges. If a stale black surface remains from an older release, close the old process from another terminal:

```bash
taskkill //F //IM agent-os.exe //T 2>/dev/null || true
taskkill //F //IM windows-agent.exe //T 2>/dev/null || true
```

Restart with `uv run windows-agent` and use `/set overlay off` to confirm that an overlay is the source. `/set overlay on` enables the process-isolated border again.

## Ctrl+C does not appear to stop a task

Press Ctrl+C once while the persistent input prompt is visible. The shell cancels the active token and closes Windows Agent-owned Playwright processes. The console itself stays open. Use `/exit` to close the console.

## The smoke test repeats after reporting success

A complete `smoke_test_site` result is deterministic evidence. v0.6 ends the run immediately when the report covers every discovered link within the configured limit. It does not ask a visual verifier to find the JSON report inside the webpage.

## No model is ready

Inside the console, run `/key status` and `/models`. Store a provider key with `/key set gemini`, `/key set openai`, or `/key set mistral`.

## A model reaches a rate limit

Keep `/model auto` selected. Windows Agent sends the same task prompt, screenshot, run history, and session context to the next configured route. Daily quota failures receive a long cooldown; transient limits use the configured cooldown.

## The browser is missing

Run:

```bash
uv run playwright install chromium
uv run windows-agent
```

Then use `/doctor` inside the console.

## Screenshots and the controlled target differ

Strict alignment is enabled by default. The capture token, lease generation, and target identity must agree before any action is executed. Use `/set target monitor:3` for a dedicated monitor.
