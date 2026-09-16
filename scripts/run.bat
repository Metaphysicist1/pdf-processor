@echo off
REM Launch PDF Studio (Windows).
setlocal
cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" run.py
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if errorlevel 1 (
  echo Python not found. Run scripts\install.bat first.
  pause
  exit /b 1
)

echo No .venv found — run scripts\install.bat first.
python run.py
