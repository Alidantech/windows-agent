# Windows Agent

**Version 0.6.0**

Windows Agent is a supervised Windows desktop agent with a persistent terminal console, provider-pluggable vision planning, model fallback, dedicated monitor/window leases, isolated browser input, Windows UI Automation, safe visual overlays, saved evidence, and deterministic website smoke tests.

The core safety rule is:

> The pixels sent to a model and the target receiving an action must belong to the same control lease.

## Start once, work interactively

Install and launch:

```bash
cd ~/Projects/windows-agent
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
windows-agent
```

`windows-agent` no longer accepts task, provider, model, target, or physical-input arguments. Start the console once and use natural-language tasks or slash commands.

```text
windows-agent

windows-agent  model auto · target monitor:3 · auto/deny
Type a task, or /help for commands.

you ❯ Open defytickets.com and smoke test every unique same-origin link
```

## Persistent console commands

| Command | Purpose |
|---|---|
| `/help` | Show all commands |
| `/status` | Show current model, target, task, queue and control settings |
| `/queue` | Show active and pending tasks |
| `/cancel` | Cancel the current task without closing the console |
| `/models [provider]` | Query models available to configured accounts |
| `/model auto` | Enable context-preserving automatic model fallback |
| `/model provider:model` | Select a specific model |
| `/key status` | Show which provider keys are configured and where |
| `/key set gemini` | Enter a key invisibly and save it in Windows Credential Manager |
| `/key delete gemini` | Delete the stored credential |
| `/set target monitor:3` | Assign the controlled monitor |
| `/set control browser` | Use isolated browser control |
| `/set physical deny` | Never use the shared Windows mouse or keyboard |
| `/set overlay on` | Enable the thin monitor border and virtual AI cursor |
| `/doctor` | Check dependencies, keys, monitors and Windows access |
| `/logs` | Show recent evidence folders |
| `/memory` | Show persistent cross-task context |
| `/memory clear` | Clear cross-task context |
| `/exit` | Cancel, clean up owned processes and close |

Tasks entered while another task is running are queued. The prompt stays usable while the worker prints progress above it. When the agent asks a question, the same input box changes to `answer ❯`.

## Terminal feed

Windows Agent uses one glyph for each relationship:

```text
⏺ open_url (1/40)
  ⎿ Open defytickets.com in the isolated browser.
  ⎿ OK Opened https://www.defytickets.com/ (HTTP 200)

⏺ smoke_test_site (2/40)
  ⎿ Test every unique same-origin link.
  ⎿ SMOKE Testing 1/6: https://www.defytickets.com/
  ⎿ OK 6 passed, 0 failed; report saved

⏺ DONE Smoke-tested all unique links.
  ⎿ evidence runs/<run-id>/browser-smoke/
```

Color communicates status, but indentation and glyphs preserve meaning in limited-color terminals.

## AI providers and auto mode

Gemini is installed by default. OpenAI and Mistral are optional:

```bash
python -m pip install -e ".[openai]"
python -m pip install -e ".[mistral]"
```

Store keys without exposing them in command history:

```text
/key set gemini
/key set openai
/key set mistral
```

Enable fallback:

```text
/model auto
```

The default candidate order is configurable with `WINDOWS_AGENT_AUTO_MODELS`. When a model returns a rate-limit, quota, transient server, DNS, connection or timeout failure, Windows Agent can retry the **same prompt, screenshot, action history and session context** on the next ready model. A failed model enters cooldown so every step does not retry it.

Manual selection:

```text
/models
/model gemini:gemini-3.5-flash-lite
/model openai:gpt-5-mini
/model mistral:mistral-small-2603
```

Model availability comes from each provider's models endpoint when its key and SDK are configured. Only use image-capable models for desktop planning.

## Dedicated monitor and independent input

Recommended settings:

```text
/set target monitor:3
/set control browser
/set physical deny
/set overlay on
```

For browser tasks, Playwright uses a page-level virtual mouse and keyboard; your physical pointer and keyboard remain yours. Desktop applications use UI Automation first. Physical fallback is denied unless you change the policy.

## Overlay safety

The overlay is a separate process. It creates only:

- four thin border-strip windows;
- one small status badge;
- one small virtual-cursor badge.

It never creates a monitor-sized transparent Tk window, so transparency failure cannot turn the assigned monitor black. Keeping Tk in a dedicated process also prevents `Tcl_AsyncDelete` cross-thread shutdown errors.

Disable it at any time:

```text
/set overlay off
```

## Deterministic smoke testing

A site smoke test is a tool operation rather than a series of guessed clicks. It inventories unique same-origin links, skips duplicates, visits each URL in isolated pages, records response and browser errors, saves screenshots, writes a report and completes directly from tool evidence.

The vision completion verifier is not asked to find a JSON report inside the webpage after the deterministic tool has already succeeded.

## Evidence

Every task writes:

```text
runs/<run-id>/
├── manifest.json
├── events.jsonl
├── agent.log
├── screens/
└── browser-smoke/
    ├── smoke-report.json
    └── *.png
```

## Configuration

Copy `.env.example` only for non-secret settings. Prefer `/key set` for credentials.

Legacy `AGENT_OS_*` variables and the `agent-os` executable are no longer supported.

## Development

```bash
python -m compileall src tests
pytest
ruff check .
```

See `docs/ARCHITECTURE.md`, `docs/TERMINAL_UI.md`, `docs/MODEL_ROUTING.md`, `docs/SAFETY.md`, `docs/TROUBLESHOOTING.md`, and `MIGRATION_V0.6.md`.
