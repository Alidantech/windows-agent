$ErrorActionPreference = "Stop"
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host "Setup complete. Run windows-agent, then use /key set gemini and /doctor"
