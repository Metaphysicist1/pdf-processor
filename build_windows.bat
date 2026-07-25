@echo off
REM ============================================================
REM  Build PDF Studio into a single Windows .exe
REM  Run this on Windows (double-click, or run in a terminal).
REM ============================================================

echo.
echo === PDF Studio - Windows build ===
echo.

REM 1) Create/refresh a virtual environment
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat

REM 2) Install dependencies + PyInstaller
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

REM 3) Build the executable from the spec
echo Building executable...
pyinstaller --noconfirm PDFStudio.spec

echo.
echo === Done! ===
echo Your app is here:  dist\PDFStudio.exe
echo Double-click it to run. No Python needed on the target machine.
echo.
pause
