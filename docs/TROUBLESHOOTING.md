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

## A greeting or question starts taking screenshots

Pull the latest `master`, synchronize, and restart the persistent console:

```bash
git pull origin master
uv sync
uv run windows-agent
```

Greetings and general questions should display a `route terminal response` line and return one direct answer. They should not create a run directory or invoke the desktop completion verifier.

Questions that explicitly require observing or controlling the computer still use the desktop route, for example:

```text
What is visible on monitor 3?
Can you open Chrome?
```

## A follow-up task starts from the monitor instead of the existing browser

Browser continuations now bind the persistent isolated browser before the first screenshot. Keep the same Windows Agent console open between tasks. Follow-ups such as `continue`, `create an account and proceed`, `fill the form`, and `log in` should show a browser-backed observation immediately.

## The agent invents account details

Windows Agent must pause before entering missing names, email addresses, phone numbers, addresses, usernames, company names, dates of birth, passwords, PINs, or verification codes. Provide each requested value through `answer ❯` or masked `secret ❯`.

Terms, privacy policies, subscriptions, and marketing consent require an explicit `I agree`. CAPTCHA and human-verification steps require you to complete the challenge in the assigned browser and then type `done`.

Sensitive answers are masked and skipped by prompt history.

## The agent repeatedly claims completion

Browser completion is checked against a fresh post-action capture. Unsupported completion claims are limited by `WINDOWS_AGENT_MAX_COMPLETION_REJECTIONS`, which defaults to `2`. After that limit, the task stops honestly instead of consuming all 40 steps.

A transition to an email-verification page proves form submission, but the account is not fully verified. The expected next behavior is an `ask_user` prompt for the verification code.

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
