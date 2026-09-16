# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for PDF Studio.

From the repository root:

    pyinstaller --noconfirm packaging/PDFStudio.spec

Output:  dist/PDFStudio.exe   (Windows)  /  dist/PDFStudio (Linux/macOS)

PyInstaller does NOT cross-compile — build on the target OS.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).resolve().parent  # packaging/ -> repo root
# When the spec is in packaging/, SPECPATH is packaging/; parent is repo root.
# PyInstaller sets SPECPATH to the directory containing the spec file.

datas = [(str(ROOT / "assets"), "assets")]
datas += collect_data_files("customtkinter")

hiddenimports = [
    "fitz",
    "pymupdf",
    "PIL._tkinter_finder",
    "pdfstudio",
    "pdfstudio.app",
    "pdfstudio.engine",
    "pdfstudio.carousel",
    "pdfstudio.dialogs",
]

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "logo.ico"),
)
