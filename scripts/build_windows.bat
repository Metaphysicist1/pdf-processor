@echo off
REM Build PDF Studio into a single Windows .exe (run on Windows).
setlocal
cd /d "%~dp0.."

echo.
echo === PDF Studio - Windows build ===
echo.

if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
)
call .venv\Scripts\activate.bat

echo Installing dependencies + PyInstaller...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo Building executable...
pyinstaller --noconfirm packaging\PDFStudio.spec

echo.
echo === Done! ===
echo Your app is here:  dist\PDFStudio.exe
echo Double-click it to run. No Python needed on the target machine.
echo.
pause
