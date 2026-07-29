#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  cat <<'MESSAGE'
uv is required.

Install from Git Bash with:
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

Then close and reopen Git Bash, verify with `uv --version`, and rerun this script.
MESSAGE
  exit 1
fi

uv sync
uv run playwright install chromium
[ -f .env ] || cp .env.example .env

printf '\nSetup complete. Start with: uv run windows-agent\n'
printf 'Inside the console, use /key set gemini and /doctor.\n'
