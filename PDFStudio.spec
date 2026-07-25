# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for PDF Studio.

Build a single-file, windowed executable:

    pip install pyinstaller
    pyinstaller PDFStudio.spec

Output:  dist/PDFStudio.exe   (Windows)  /  dist/PDFStudio (Linux/macOS)

Note: PyInstaller does NOT cross-compile. Run it on Windows to get a .exe,
on macOS to get a macOS binary, etc.
"""

from PyInstaller.utils.hooks import collect_data_files

# Only bundle what isn't already handled by PyInstaller's built-in hooks.
# (pymupdf / fitz and Pillow have working hooks; we add customtkinter's theme
# JSON/assets and our own assets folder.)
datas = [("assets", "assets")]
datas += collect_data_files("customtkinter")

hiddenimports = ["fitz", "pymupdf", "PIL._tkinter_finder"]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "PySide6", "PyQt5", "PyQt6", "matplotlib", "numpy", "scipy"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PDFStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed app, no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/logo.ico",
)
