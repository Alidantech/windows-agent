# Migration to Windows Agent v0.6

## Pull and reinstall

```bash
cd ~/Projects/windows-agent
git pull origin master
rm -rf .venv
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

Optional providers:

```bash
python -m pip install -e ".[openai,mistral]"
```

## Start the new console

```bash
windows-agent
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

## Configuration rename is now final

Only `WINDOWS_AGENT_*` settings are loaded. Remove stale `AGENT_OS_*` entries from `.env`.

## Credentials

Use `/key set PROVIDER` to save keys in Windows Credential Manager. Existing environment variables still work for unattended setups:

- `GEMINI_API_KEY`
- `OPENAI_API_KEY`
- `MISTRAL_API_KEY`

## Runtime folders

The runtime state folder is `.windows-agent/`. The old `.agent-os/` folder can be deleted after confirming the new browser profile works.
