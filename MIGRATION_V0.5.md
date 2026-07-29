# Migration to Windows Agent v0.5

The product and package are now named **Windows Agent**. Gemini remains the default provider, while OpenAI and Mistral are optional adapters.

## Update your checkout

```bash
git pull origin master
rm -rf .venv
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

## Command rename

Use:

```bash
windows-agent doctor
```

The old `agent-os` command remains available temporarily.

## Environment rename

New configuration uses `WINDOWS_AGENT_*`:

```env
WINDOWS_AGENT_PROVIDER=gemini
WINDOWS_AGENT_MODEL=gemini-3.5-flash-lite
WINDOWS_AGENT_TARGET=monitor:3
WINDOWS_AGENT_BROWSER_PROFILE_DIR=.windows-agent/browser-profile
```

Existing `AGENT_OS_*` variables still work. Provider credentials keep their standard names: `GEMINI_API_KEY`, `OPENAI_API_KEY`, and `MISTRAL_API_KEY`.
