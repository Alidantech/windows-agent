$ErrorActionPreference = "Stop"
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host "Setup complete. Select a provider and add its API key to .env, then run: windows-agent doctor"
