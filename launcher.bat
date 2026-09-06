@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
  if errorlevel 1 pause & exit /b %errorlevel%
)
".venv\Scripts\python.exe" -m draft_tool.launcher
if errorlevel 1 pause
