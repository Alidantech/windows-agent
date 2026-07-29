#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
[ -f .env ] || cp .env.example .env
printf '\nSetup complete. Run windows-agent, then use /key set gemini and /doctor\n'
