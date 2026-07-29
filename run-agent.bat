@echo off
setlocal
if not exist .venv\Scripts\python.exe (
  echo Missing .venv. Run scripts\setup.ps1 or create the virtual environment first.
  exit /b 1
)
call .venv\Scripts\activate.bat
agent-os chat --target active-window
