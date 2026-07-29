@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Virtual environment not found. Run scripts\setup.ps1 first.
  exit /b 1
)
call .venv\Scripts\activate.bat
windows-agent chat
endlocal
