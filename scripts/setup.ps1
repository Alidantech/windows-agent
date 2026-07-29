$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is required." -ForegroundColor Red
    Write-Host 'Install it with: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    Write-Host "Close and reopen the terminal, verify with 'uv --version', then rerun this script."
    exit 1
}

uv sync
uv run playwright install chromium
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Write-Host "Setup complete. Start with: uv run windows-agent"
Write-Host "Inside the console, use /key set gemini and /doctor."
