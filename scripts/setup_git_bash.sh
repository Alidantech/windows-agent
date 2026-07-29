#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e .

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "Setup complete. Add GEMINI_API_KEY to .env, then run:"
echo "  source .venv/Scripts/activate"
echo "  agent-os doctor"
