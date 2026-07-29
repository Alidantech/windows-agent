# Migration to Windows Agent v0.6

## Pull and synchronize with uv

Install uv once:

```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen Git Bash, then run:

```bash
cd ~/Projects/windows-agent
deactivate 2>/dev/null || true
rm -rf .venv
git pull origin master
uv sync
uv run playwright install chromium
```

Start the console without activating an environment:

```bash
uv run windows-agent
```

The old argument-heavy form has been removed. Do not run:

```text
windows-agent --provider ... run "..." --target ...
```

Use the persistent console instead:

```text
/key set gemini
/set target monitor:3
/set control browser
/set physical deny
/model auto
Open defytickets.com and smoke test every unique same-origin link
```

## Configuration rename is final

Only `WINDOWS_AGENT_*` settings are loaded. Remove stale `AGENT_OS_*` entries from `.env`.

## Credentials

Use `/key set PROVIDER` to save keys in Windows Credential Manager. Existing environment variables still work for unattended setups:

- `GEMINI_API_KEY`
- `OPENAI_API_KEY`
- `MISTRAL_API_KEY`

## Runtime folders

The runtime state folder is `.windows-agent/`. The old `.agent-os/` folder can be deleted after confirming the new browser profile works.

## Python project management

The supported workflow is now uv-only. See `MIGRATION_UV.md` and `docs/UV.md`. Do not manually create, activate, or install into `.venv`.
