#!/usr/bin/env python3
"""dialogs.py - native OS file dialogs with a Tk fallback.

Tkinter's built-in file chooser looks dated on Linux (old Motif style). On
GNOME/Ubuntu we shell out to ``zenity`` to get the real GTK file picker; if
``zenity`` is not present we fall back to ``tkinter.filedialog`` so the app
still works everywhere.

Filters are passed as ``[(label, [patterns...]), ...]`` e.g.
``[("PDF files", ["*.pdf"]), ("All files", ["*"])]``.
"""

from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache
from tkinter import filedialog
from typing import Optional, Sequence

Filter = tuple[str, list[str]]

_TIMEOUT = 600  # seconds a dialog may stay open before we give up


@lru_cache(maxsize=1)
def zenity_path() -> Optional[str]:
    return shutil.which("zenity")


def available() -> bool:
    """True when a native (zenity) dialog can be used."""
    return zenity_path() is not None


def _tk_filetypes(filters: Optional[Sequence[Filter]]):
    if not filters:
        return [("All files", "*.*")]
    return [(label, " ".join(patterns)) for label, patterns in filters]


def _zenity(args: list[str]) -> Optional[str]:
    exe = zenity_path()
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:  # 1 = cancelled / closed
        return ""
    return proc.stdout.rstrip("\n")


def _filter_args(filters: Optional[Sequence[Filter]]) -> list[str]:
    args: list[str] = []
    for label, patterns in filters or []:
        args.append(f"--file-filter={label} | {' '.join(patterns)}")
    return args


def open_file(title: str, filters: Optional[Sequence[Filter]] = None) -> str:
    """Choose a single existing file. Returns "" if cancelled."""
    if available():
        out = _zenity(["--file-selection", f"--title={title}", *_filter_args(filters)])
        return out or ""
    return filedialog.askopenfilename(title=title, filetypes=_tk_filetypes(filters)) or ""


def open_files(title: str, filters: Optional[Sequence[Filter]] = None) -> list[str]:
    """Choose one or more existing files. Returns [] if cancelled."""
    if available():
        out = _zenity([
            "--file-selection", "--multiple", "--separator=\n",
            f"--title={title}", *_filter_args(filters),
        ])
        return [line for line in (out or "").split("\n") if line]
    return list(filedialog.askopenfilenames(title=title, filetypes=_tk_filetypes(filters)))


def save_file(
    title: str,
    default_name: str = "output",
    filters: Optional[Sequence[Filter]] = None,
    default_extension: str = "",
) -> str:
    """Choose a path to save to. Returns "" if cancelled."""
    if available():
        out = _zenity([
            "--file-selection", "--save", "--confirm-overwrite",
            f"--filename={default_name}", f"--title={title}", *_filter_args(filters),
        ])
        return out or ""
    return filedialog.asksaveasfilename(
        title=title,
        initialfile=default_name,
        defaultextension=default_extension,
        filetypes=_tk_filetypes(filters),
    ) or ""


def pick_directory(title: str) -> str:
    """Choose a directory. Returns "" if cancelled."""
    if available():
        out = _zenity(["--file-selection", "--directory", f"--title={title}"])
        return out or ""
    return filedialog.askdirectory(title=title) or ""
