@echo off
REM Install PDF Studio deps into a local .venv (Windows).
setlocal
cd /d "%~dp0.."

where python >nul 2>&1
if errorlevel 1 (
  echo Python not found. Install Python 3.10+ from https://www.python.org/downloads/
  echo Tick "Add Python to PATH" during setup, then re-run this script.
  pause
  exit /b 1
)

echo ==^> Creating virtual environment (.venv)
python -m venv .venv
call .venv\Scripts\activate.bat

echo ==^> Installing dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo Done. Start the app with:
echo   scripts\run.bat
echo   or double-click: run.bat  (in the project root)
echo.
pause
