#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
[ -f .env ] || cp .env.example .env
printf '\nSetup complete. Select a provider and add its API key to .env, then run: windows-agent doctor\n'
