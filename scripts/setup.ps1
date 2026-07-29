$ErrorActionPreference = "Stop"
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host "Setup complete. Add GEMINI_API_KEY to .env, then run: agent-os doctor"
