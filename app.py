#!/usr/bin/env python3
"""app.py - PDF Studio desktop app.

A modern, dark-themed desktop UI (CustomTkinter) that unifies every PDF tool in
this repo behind one interface:

    - Merge          : combine several PDFs into one (drag to reorder)
    - Compress       : shrink a PDF by recompressing images + streams
    - Remove Pages   : delete specific pages from a PDF
    - PDF to Images  : split a PDF into carousel images (Instagram)
    - Images to PDF  : combine images into one PDF (LinkedIn document post)

All heavy work runs in a background thread; the UI stays responsive and shows a
live progress bar. Business logic lives in ``pdf_engine.py``.

Run:  python app.py
Dependencies (see requirements.txt): customtkinter, pypdf, pymupdf, Pillow.
"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

import native_dialog as dialogs
import pdf_engine as engine

PDF_FILTER = [("PDF files", ["*.pdf"]), ("All files", ["*"])]
IMAGE_FILTER = [("Images", ["*.png", "*.jpg", "*.jpeg"]), ("All files", ["*"])]

# --- Theme -----------------------------------------------------------------

APP_NAME = "PDF Studio"
APP_VERSION = "1.0"

# Resolve assets both when run from source and when frozen by PyInstaller.
if getattr(sys, "frozen", False):
    _BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
else:
    _BASE = Path(__file__).resolve().parent
ASSETS = _BASE / "assets"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Matrix-inspired palette: near-black with green-tinted surfaces and neon-green accents.
COL_BG = "#080B08"          # window background (near-black)
COL_SIDEBAR = "#0C110C"     # sidebar
COL_CARD = "#111811"        # cards / panels
COL_CARD_2 = "#18221A"      # inputs / nested
COL_STROKE = "#25382A"      # subtle green-tinted borders
COL_TEXT = "#E7F5E7"        # soft green-white
COL_MUTED = "#7E947E"       # muted green-gray
COL_ACCENT = "#00C853"      # matrix green
COL_ACCENT_HOVER = "#00E676"
COL_ACCENT_2 = "#39FF7A"    # bright glow green (progress)
COL_OK = "#00E676"
COL_ERR = "#FF5C5C"
COL_WARN = "#F5B23D"

FONT_FAMILY = "Segoe UI"


def f(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


# --- Reusable widgets ------------------------------------------------------


class FileList(ctk.CTkScrollableFrame):
    """A reorderable list of file paths with per-row remove and move buttons."""

    def __init__(self, master, reorder: bool = True, empty_hint: str = "No files added yet"):
        super().__init__(master, fg_color=COL_CARD_2, corner_radius=14, height=170)
        self.reorder = reorder
        self.empty_hint = empty_hint
        self._paths: list[str] = []
        self._hint = ctk.CTkLabel(self, text=empty_hint, text_color=COL_MUTED, font=f(13))
        self._render()

    def get_paths(self) -> list[str]:
        return list(self._paths)

    def clear(self) -> None:
        self._paths.clear()
        self._render()

    def add(self, paths: list[str]) -> None:
        for p in paths:
            if p and p not in self._paths:
                self._paths.append(p)
        self._render()

    def set_single(self, path: str) -> None:
        self._paths = [path] if path else []
        self._render()

    def _move(self, i: int, delta: int) -> None:
        j = i + delta
        if 0 <= j < len(self._paths):
            self._paths[i], self._paths[j] = self._paths[j], self._paths[i]
            self._render()

    def _remove(self, i: int) -> None:
        del self._paths[i]
        self._render()

    def _render(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        if not self._paths:
            self._hint = ctk.CTkLabel(self, text=self.empty_hint, text_color=COL_MUTED, font=f(13))
            self._hint.pack(pady=24)
            return
        for i, path in enumerate(self._paths):
            row = ctk.CTkFrame(self, fg_color=COL_CARD, corner_radius=10)
            row.pack(fill="x", padx=6, pady=4)
            badge = ctk.CTkLabel(row, text=f"{i + 1}", width=26, height=26,
                                 fg_color=COL_ACCENT, corner_radius=8,
                                 text_color="white", font=f(12, "bold"))
            badge.pack(side="left", padx=(8, 8), pady=8)
            name = ctk.CTkLabel(row, text=Path(path).name, anchor="w",
                                text_color=COL_TEXT, font=f(13))
            name.pack(side="left", fill="x", expand=True, padx=(0, 8))
            remove = ctk.CTkButton(row, text="\u2715", width=30, height=28,
                                   fg_color="transparent", hover_color=COL_ERR,
                                   text_color=COL_MUTED, font=f(14, "bold"),
                                   command=lambda i=i: self._remove(i))
            remove.pack(side="right", padx=(0, 8))
            if self.reorder:
                down = ctk.CTkButton(row, text="\u25BC", width=30, height=28,
                                     fg_color="transparent", hover_color=COL_CARD_2,
                                     text_color=COL_MUTED, font=f(11),
                                     command=lambda i=i: self._move(i, 1))
                down.pack(side="right")
                up = ctk.CTkButton(row, text="\u25B2", width=30, height=28,
                                   fg_color="transparent", hover_color=COL_CARD_2,
                                   text_color=COL_MUTED, font=f(11),
                                   command=lambda i=i: self._move(i, -1))
                up.pack(side="right")


class Field(ctk.CTkFrame):
    """A labeled option row: a caption above a supplied widget factory."""

    def __init__(self, master, label: str, hint: str = ""):
        super().__init__(master, fg_color="transparent")
        top = ctk.CTkLabel(self, text=label, anchor="w", text_color=COL_TEXT, font=f(13, "bold"))
        top.pack(fill="x")
        if hint:
            ctk.CTkLabel(self, text=hint, anchor="w", text_color=COL_MUTED, font=f(11)).pack(fill="x")


class MessageDialog(ctk.CTkToplevel):
    """A modal message window styled to match the app (replaces OS messageboxes)."""

    STYLES = {
        "success": ("\u2713", COL_OK, "Done"),
        "info": ("\u2139", COL_ACCENT, "Info"),
        "warning": ("!", COL_WARN, "Heads up"),
        "error": ("\u2715", COL_ERR, "Something went wrong"),
    }

    def __init__(self, root, kind: str, title: str, message: str):
        super().__init__(root, fg_color=COL_CARD)
        glyph, color, _ = self.STYLES.get(kind, self.STYLES["info"])
        self.title(title)
        self.resizable(False, False)
        self.transient(root)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=26, pady=(24, 6))
        ctk.CTkLabel(header, text=glyph, width=46, height=46, corner_radius=23,
                     fg_color=color, text_color="#06110A", font=f(22, "bold")).pack(side="left")
        ctk.CTkLabel(header, text=title, text_color=COL_TEXT, font=f(18, "bold"),
                     justify="left").pack(side="left", padx=16)

        ctk.CTkLabel(self, text=message, text_color=COL_MUTED, font=f(13),
                     justify="left", wraplength=440, anchor="w").pack(
            fill="x", padx=26, pady=(2, 18))

        btn = ctk.CTkButton(self, text="OK", width=120, height=40, corner_radius=10,
                            fg_color=COL_ACCENT, hover_color=COL_ACCENT_HOVER,
                            text_color="#06110A", font=f(14, "bold"), command=self._close)
        btn.pack(pady=(0, 22))

        self.bind("<Return>", lambda _e: self._close())
        self.bind("<Escape>", lambda _e: self._close())
        self._center(root)
        self.after(10, self._grab)
        btn.focus_set()

    def _grab(self) -> None:
        try:
            self.grab_set()
        except Exception:  # noqa: BLE001
            pass

    def _center(self, root) -> None:
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        try:
            px, py = root.winfo_rootx(), root.winfo_rooty()
            pw, ph = root.winfo_width(), root.winfo_height()
            x, y = px + (pw - w) // 2, py + (ph - h) // 3
        except Exception:  # noqa: BLE001
            x = y = 120
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _close(self) -> None:
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001
            pass
        self.destroy()


def show_message(widget, kind: str, title: str, message: str) -> None:
    """Show a modal, app-styled message dialog centered over the main window."""
    root = widget.winfo_toplevel()
    dlg = MessageDialog(root, kind, title, message)
    root.wait_window(dlg)


# --- Base page -------------------------------------------------------------


class BasePage(ctk.CTkFrame):
    """Common scaffolding: header, action bar, progress, threaded execution.

    A fixed header sits at the top, a fixed action bar at the bottom, and the
    tool's options live in a scrollable body in between.
    """

    title = "Tool"
    subtitle = ""
    icon = "\u25A0"
    run_label = "Run"

    def __init__(self, master):
        super().__init__(master, fg_color=COL_BG, corner_radius=0)
        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._built = False
        self._build_header()
        self._build_actionbar()  # packed to bottom before body claims the middle
        self.body = ctk.CTkScrollableFrame(self, fg_color=COL_BG)
        self.body.pack(fill="both", expand=True, padx=20, pady=(0, 4))

    def ensure_built(self) -> None:
        """Build the tool's option widgets lazily, on first view (snappy startup)."""
        if not self._built:
            self._built = True
            self.build_body(self.body)

    # -- layout --
    def _build_header(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", side="top", padx=32, pady=(28, 8))
        ctk.CTkLabel(head, text=f"{self.icon}  {self.title}", anchor="w",
                     text_color=COL_TEXT, font=f(26, "bold")).pack(fill="x")
        if self.subtitle:
            ctk.CTkLabel(head, text=self.subtitle, anchor="w", justify="left",
                         text_color=COL_MUTED, font=f(14)).pack(fill="x", pady=(2, 0))

    def _build_actionbar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=COL_SIDEBAR, corner_radius=0, height=84)
        bar.pack(fill="x", side="bottom")
        bar = ctk.CTkFrame(bar, fg_color="transparent")
        bar.pack(fill="x", padx=32, pady=20)
        self.run_btn = ctk.CTkButton(bar, text=self.run_label, height=44, width=180,
                                     fg_color=COL_ACCENT, hover_color=COL_ACCENT_HOVER,
                                     text_color="#06110A", font=f(15, "bold"), corner_radius=12,
                                     command=self.on_run)
        self.run_btn.pack(side="left")
        self.progress = ctk.CTkProgressBar(bar, height=10, corner_radius=6,
                                           progress_color=COL_ACCENT_2)
        self.progress.set(0)
        self.progress.pack(side="left", fill="x", expand=True, padx=16)
        self.status = ctk.CTkLabel(bar, text="Ready", text_color=COL_MUTED,
                                   font=f(13), width=180, anchor="e")
        self.status.pack(side="right")

    def card(self, parent, title: str = "") -> ctk.CTkFrame:
        wrap = ctk.CTkFrame(parent, fg_color=COL_CARD, corner_radius=16,
                            border_width=1, border_color=COL_STROKE)
        wrap.pack(fill="x", pady=8)
        inner = ctk.CTkFrame(wrap, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=18)
        if title:
            ctk.CTkLabel(inner, text=title, anchor="w", text_color=COL_TEXT,
                         font=f(15, "bold")).pack(fill="x", pady=(0, 10))
        return inner

    # -- overridable --
    def build_body(self, parent) -> None:  # pragma: no cover - UI
        raise NotImplementedError

    def collect_job(self) -> Optional[Callable[[engine.Progress], dict]]:
        """Return a zero-arg-ish callable taking a progress cb, or None if invalid."""
        raise NotImplementedError

    def describe_result(self, result: dict) -> str:
        return "Done."

    # -- execution --
    def on_run(self) -> None:
        try:
            job = self.collect_job()
        except engine.EngineError as exc:
            show_message(self, "error", "Check your input", str(exc))
            return
        if job is None:
            return
        self.run_btn.configure(state="disabled")
        self.progress.set(0)
        self._set_status("Working...", COL_MUTED)

        def worker() -> None:
            def prog(fr: float, msg: str) -> None:
                self._queue.put(("progress", fr, msg))
            try:
                result = job(prog)
                self._queue.put(("done", result))
            except engine.EngineError as exc:
                self._queue.put(("error", str(exc)))
            except Exception as exc:  # noqa: BLE001
                self._queue.put(("error", f"Unexpected error: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(60, self._poll)

    def _poll(self) -> None:
        try:
            while True:
                item = self._queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _, fr, msg = item
                    self.progress.set(fr)
                    self._set_status(msg, COL_MUTED)
                elif kind == "done":
                    self.progress.set(1.0)
                    self._set_status("Done", COL_OK)
                    self.run_btn.configure(state="normal")
                    result = item[1]
                    if result.get("warning"):
                        show_message(self, "warning", "Heads up", result["warning"])
                    show_message(self, "success", "Done", self.describe_result(result))
                    return
                elif kind == "error":
                    self.progress.set(0)
                    self._set_status("Failed", COL_ERR)
                    self.run_btn.configure(state="normal")
                    show_message(self, "error", "Something went wrong", item[1])
                    return
        except queue.Empty:
            pass
        self.after(60, self._poll)

    def _set_status(self, text: str, color: str) -> None:
        self.status.configure(text=text, text_color=color)

    # -- dialog helpers (native GTK/zenity when available, else Tk) --
    def pick_pdfs(self) -> list[str]:
        return dialogs.open_files("Select PDF files", PDF_FILTER)

    def pick_pdf(self) -> str:
        return dialogs.open_file("Select a PDF", PDF_FILTER)

    def pick_images(self) -> list[str]:
        return dialogs.open_files("Select images", IMAGE_FILTER)

    def save_pdf(self, default: str = "output.pdf") -> str:
        return dialogs.save_file("Save PDF as", default, PDF_FILTER, default_extension=".pdf")

    def pick_dir(self) -> str:
        return dialogs.pick_directory("Select output folder")


def outlined_button(master, text: str, command) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=text, command=command, height=40,
                         fg_color=COL_CARD_2, hover_color=COL_STROKE,
                         border_width=1, border_color=COL_ACCENT,
                         text_color=COL_TEXT, font=f(13, "bold"), corner_radius=10)


class PathPicker(ctk.CTkFrame):
    """An entry + browse button for choosing an output path."""

    def __init__(self, master, on_browse: Callable[[], str], placeholder: str):
        super().__init__(master, fg_color="transparent")
        self.entry = ctk.CTkEntry(self, height=40, fg_color=COL_CARD_2,
                                  border_color=COL_STROKE, text_color=COL_TEXT,
                                  placeholder_text=placeholder, font=f(13))
        self.entry.pack(side="left", fill="x", expand=True)
        self._on_browse = on_browse
        btn = outlined_button(self, "Browse", self._browse)
        btn.configure(width=110)
        btn.pack(side="left", padx=(10, 0))

    def _browse(self) -> None:
        chosen = self._on_browse()
        if chosen:
            self.set(chosen)

    def get(self) -> str:
        return self.entry.get().strip()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, value)


# --- Pages -----------------------------------------------------------------


class MergePage(BasePage):
    title = "Merge PDFs"
    subtitle = "Combine several PDFs into one. Reorder them, then export."
    icon = "\u29C9"
    run_label = "Merge PDFs"

    def build_body(self, parent) -> None:
        c = self.card(parent, "Source PDFs")
        btns = ctk.CTkFrame(c, fg_color="transparent")
        btns.pack(fill="x", pady=(0, 12))
        outlined_button(btns, "+  Add PDFs", self._add).pack(side="left")
        outlined_button(btns, "Clear all", lambda: self.files.clear()).pack(side="left", padx=10)
        self.files = FileList(c, reorder=True, empty_hint="Add two or more PDFs to merge")
        self.files.pack(fill="x")

        o = self.card(parent, "Output")
        self.out = PathPicker(o, lambda: self.save_pdf("merged.pdf"), "Choose where to save the merged PDF")
        self.out.pack(fill="x")

    def _add(self) -> None:
        self.files.add(self.pick_pdfs())

    def collect_job(self):
        paths = self.files.get_paths()
        if len(paths) < 2:
            raise engine.EngineError("Add at least two PDFs to merge.")
        out = self.out.get()
        if not out:
            raise engine.EngineError("Choose an output file.")
        return lambda prog: engine.merge_pdfs(paths, out, progress=prog)

    def describe_result(self, result: dict) -> str:
        return (f"Merged {result['files']} PDFs into {result['pages']} pages.\n\n"
                f"Saved to:\n{result['output']}\n({result['mb']:.2f} MB)")


class CompressPage(BasePage):
    title = "Compress PDF"
    subtitle = "Shrink a PDF by recompressing its images and content streams."
    icon = "\u2193"
    run_label = "Compress PDF"

    def build_body(self, parent) -> None:
        c = self.card(parent, "Source PDF")
        outlined_button(c, "Choose PDF", self._choose).pack(anchor="w", pady=(0, 12))
        self.files = FileList(c, reorder=False, empty_hint="No PDF selected")
        self.files.pack(fill="x")

        q = self.card(parent, "Image quality")
        self.qval = ctk.CTkLabel(q, text="65", text_color=COL_ACCENT_2, font=f(13, "bold"))
        self.qval.pack(anchor="w")
        self.quality = ctk.CTkSlider(q, from_=10, to=100, number_of_steps=90,
                                     progress_color=COL_ACCENT, button_color=COL_ACCENT_2,
                                     command=lambda v: self.qval.configure(text=f"{int(v)}"))
        self.quality.set(65)
        self.quality.pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(q, text="Lower = smaller file, blurrier images. 60-80 is a good balance.",
                     text_color=COL_MUTED, font=f(11)).pack(anchor="w")

        o = self.card(parent, "Output")
        self.out = PathPicker(o, lambda: self.save_pdf("compressed.pdf"), "Choose where to save the compressed PDF")
        self.out.pack(fill="x")

    def _choose(self) -> None:
        p = self.pick_pdf()
        if p:
            self.files.set_single(p)
            if not self.out.get():
                self.out.set(str(Path(p).with_name(Path(p).stem + "_compressed.pdf")))

    def collect_job(self):
        paths = self.files.get_paths()
        if not paths:
            raise engine.EngineError("Choose a PDF to compress.")
        out = self.out.get()
        if not out:
            raise engine.EngineError("Choose an output file.")
        quality = int(self.quality.get())
        return lambda prog: engine.compress_pdf(paths[0], out, quality=quality, progress=prog)

    def describe_result(self, result: dict) -> str:
        return (f"Original: {result['original_mb']:.2f} MB\n"
                f"New:      {result['new_mb']:.2f} MB\n"
                f"Saved:    {result['saved_pct']:.1f}%\n\n"
                f"Saved to:\n{result['output']}")


class RemovePage(BasePage):
    title = "Remove Pages"
    subtitle = "Delete specific pages from a PDF (e.g. 2, 5, 9)."
    icon = "\u2702"
    run_label = "Remove Pages"

    def build_body(self, parent) -> None:
        c = self.card(parent, "Source PDF")
        outlined_button(c, "Choose PDF", self._choose).pack(anchor="w", pady=(0, 12))
        self.files = FileList(c, reorder=False, empty_hint="No PDF selected")
        self.files.pack(fill="x")
        self.count_lbl = ctk.CTkLabel(c, text="", text_color=COL_ACCENT_2, font=f(12, "bold"))
        self.count_lbl.pack(anchor="w", pady=(8, 0))

        p = self.card(parent, "Pages to remove")
        self.pages = ctk.CTkEntry(p, height=40, fg_color=COL_CARD_2, border_color=COL_STROKE,
                                  text_color=COL_TEXT, placeholder_text="e.g. 2, 5, 9", font=f(13))
        self.pages.pack(fill="x")
        ctk.CTkLabel(p, text="Comma-separated, 1-based page numbers.",
                     text_color=COL_MUTED, font=f(11)).pack(anchor="w", pady=(4, 0))

        o = self.card(parent, "Output")
        self.out = PathPicker(o, lambda: self.save_pdf("edited.pdf"), "Choose where to save the result")
        self.out.pack(fill="x")

    def _choose(self) -> None:
        p = self.pick_pdf()
        if not p:
            return
        self.files.set_single(p)
        try:
            n = engine.pdf_page_count(p)
            self.count_lbl.configure(text=f"This PDF has {n} pages.")
        except engine.EngineError as exc:
            self.count_lbl.configure(text=str(exc), text_color=COL_ERR)
        if not self.out.get():
            self.out.set(str(Path(p).with_name(Path(p).stem + "_edited.pdf")))

    def collect_job(self):
        paths = self.files.get_paths()
        if not paths:
            raise engine.EngineError("Choose a PDF.")
        raw = self.pages.get().replace(" ", "")
        if not raw:
            raise engine.EngineError("Enter the page numbers to remove.")
        try:
            nums = [int(x) for x in raw.split(",") if x]
        except ValueError:
            raise engine.EngineError("Pages must be numbers separated by commas.")
        out = self.out.get()
        if not out:
            raise engine.EngineError("Choose an output file.")
        return lambda prog: engine.remove_pages(paths[0], out, nums, progress=prog)

    def describe_result(self, result: dict) -> str:
        removed = ", ".join(map(str, result["removed"]))
        return (f"Removed page(s): {removed}\n"
                f"Kept {result['kept']} pages.\n\n"
                f"Saved to:\n{result['output']}\n({result['mb']:.2f} MB)")


SIZE_LABELS = {
    "4x5 - 1080x1350 (portrait)": "4x5",
    "1x1 - 1080x1080 (square)": "1x1",
    "9x16 - 1080x1920 (story)": "9x16",
}


class SplitPage(BasePage):
    title = "PDF to Images"
    subtitle = "Turn each PDF page into a crisp carousel image for Instagram."
    icon = "\u25A6"
    run_label = "Export Images"

    def build_body(self, parent) -> None:
        c = self.card(parent, "Source PDF")
        outlined_button(c, "Choose PDF", self._choose).pack(anchor="w", pady=(0, 12))
        self.files = FileList(c, reorder=False, empty_hint="No PDF selected")
        self.files.pack(fill="x")

        opt = self.card(parent, "Carousel options")
        grid = ctk.CTkFrame(opt, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1), weight=1, uniform="a")

        Field(grid, "Aspect / size").grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.size = ctk.CTkOptionMenu(grid, values=list(SIZE_LABELS), fg_color=COL_CARD_2,
                                      button_color=COL_ACCENT, button_hover_color=COL_ACCENT_HOVER,
                                      font=f(13), dropdown_font=f(13))
        self.size.set(list(SIZE_LABELS)[0])
        self.size.grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(2, 14))

        Field(grid, "Format").grid(row=0, column=1, sticky="w")
        self.fmt = ctk.CTkSegmentedButton(grid, values=["png", "jpg"],
                                          selected_color=COL_ACCENT,
                                          selected_hover_color=COL_ACCENT_HOVER, font=f(13))
        self.fmt.set("png")
        self.fmt.grid(row=1, column=1, sticky="ew", pady=(2, 14))

        Field(grid, "Fit mode", "pad = letterbox (no crop), cover = crop to fill").grid(
            row=2, column=0, sticky="w", padx=(0, 12))
        self.fit = ctk.CTkSegmentedButton(grid, values=["pad", "cover"],
                                          selected_color=COL_ACCENT,
                                          selected_hover_color=COL_ACCENT_HOVER, font=f(13),
                                          command=self._toggle_bg)
        self.fit.set("pad")
        self.fit.grid(row=3, column=0, sticky="ew", padx=(0, 12), pady=(2, 14))

        Field(grid, "Max slides", "Blank = all pages").grid(row=2, column=1, sticky="w")
        self.max_slides = ctk.CTkEntry(grid, height=36, fg_color=COL_CARD_2, border_color=COL_STROKE,
                                       text_color=COL_TEXT, placeholder_text="e.g. 20", font=f(13))
        self.max_slides.grid(row=3, column=1, sticky="ew", pady=(2, 14))

        self.bg_field = Field(grid, "Pad background (hex)", "Blank = auto-sample page corners")
        self.bg_field.grid(row=4, column=0, sticky="w", padx=(0, 12))
        self.bg = ctk.CTkEntry(grid, height=36, fg_color=COL_CARD_2, border_color=COL_STROKE,
                               text_color=COL_TEXT, placeholder_text="#FFFFFF", font=f(13))
        self.bg.grid(row=5, column=0, sticky="ew", padx=(0, 12))

        o = self.card(parent, "Output folder")
        self.out = PathPicker(o, self.pick_dir, "Choose a folder for the slide images")
        self.out.pack(fill="x")

    def _toggle_bg(self, _value=None) -> None:
        state = "normal" if self.fit.get() == "pad" else "disabled"
        self.bg.configure(state=state)

    def _choose(self) -> None:
        p = self.pick_pdf()
        if p:
            self.files.set_single(p)
            if not self.out.get():
                self.out.set(str(Path(p).with_suffix("")) + "_slides")

    def collect_job(self):
        paths = self.files.get_paths()
        if not paths:
            raise engine.EngineError("Choose a PDF.")
        out = self.out.get()
        if not out:
            raise engine.EngineError("Choose an output folder.")
        size = SIZE_LABELS[self.size.get()]
        fit = self.fit.get()
        fmt = self.fmt.get()
        max_raw = self.max_slides.get().strip()
        max_slides = None
        if max_raw:
            try:
                max_slides = int(max_raw)
            except ValueError:
                raise engine.EngineError("Max slides must be a whole number.")
        bg = None
        if fit == "pad" and self.bg.get().strip():
            try:
                bg = _parse_hex(self.bg.get().strip())
            except ValueError:
                raise engine.EngineError("Background must be a hex color like #FFFFFF.")
        return lambda prog: engine.split_pdf_to_images(
            paths[0], out, size=size, fit=fit, bg=bg, fmt=fmt,
            max_slides=max_slides, progress=prog)

    def describe_result(self, result: dict) -> str:
        return (f"Exported {result['count']} images at {result['size']} "
                f"(fit={result['fit']}).\n\nFolder:\n{result['outdir']}")


class BuildPage(BasePage):
    title = "Images to PDF"
    subtitle = "Combine images into a single PDF, ready for a LinkedIn document post."
    icon = "\u2750"
    run_label = "Build PDF"

    def build_body(self, parent) -> None:
        c = self.card(parent, "Images")
        btns = ctk.CTkFrame(c, fg_color="transparent")
        btns.pack(fill="x", pady=(0, 12))
        outlined_button(btns, "+  Add images", self._add).pack(side="left")
        outlined_button(btns, "Add folder", self._add_folder).pack(side="left", padx=10)
        outlined_button(btns, "Clear all", lambda: self.files.clear()).pack(side="left")
        self.files = FileList(c, reorder=True, empty_hint="Add PNG / JPG images (drag to reorder)")
        self.files.pack(fill="x")
        ctk.CTkLabel(c, text="Order top-to-bottom = PDF page order.",
                     text_color=COL_MUTED, font=f(11)).pack(anchor="w", pady=(8, 0))

        o = self.card(parent, "Output")
        self.out = PathPicker(o, lambda: self.save_pdf("carousel.pdf"), "Choose where to save the PDF")
        self.out.pack(fill="x")

    def _add(self) -> None:
        self.files.add(self.pick_images())

    def _add_folder(self) -> None:
        d = self.pick_dir()
        if not d:
            return
        imgs = sorted(
            (str(p) for p in Path(d).iterdir()
             if p.suffix.lower() in engine.carousel.IMAGE_EXTENSIONS),
            key=lambda s: engine.carousel.natural_key(Path(s)),
        )
        self.files.add(imgs)

    def collect_job(self):
        paths = self.files.get_paths()
        if not paths:
            raise engine.EngineError("Add at least one image.")
        out = self.out.get()
        if not out:
            raise engine.EngineError("Choose an output file.")
        return lambda prog: engine.build_pdf_from_images(paths, out, progress=prog)

    def describe_result(self, result: dict) -> str:
        return (f"Built a {result['pages']}-page PDF.\n\n"
                f"Saved to:\n{result['output']}\n({result['mb']:.2f} MB)")


def _parse_hex(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
        raise ValueError("bad hex")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# --- App shell -------------------------------------------------------------


class App(ctk.CTk):
    PAGES = [
        ("Merge", MergePage),
        ("Compress", CompressPage),
        ("Remove Pages", RemovePage),
        ("PDF \u2192 Images", SplitPage),
        ("Images \u2192 PDF", BuildPage),
    ]

    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1080x760")
        self.minsize(920, 640)
        self.configure(fg_color=COL_BG)
        self._logo_img = None
        self._set_icon()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()

        self.container = ctk.CTkFrame(self, fg_color=COL_BG)
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.pages: dict[str, BasePage] = {}
        for name, cls in self.PAGES:
            page = cls(self.container)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = page

        self.select(self.PAGES[0][0])

    def _set_icon(self) -> None:
        logo = ASSETS / "logo.png"
        if logo.is_file():
            try:
                icon = tk.PhotoImage(file=str(logo))
                factor = max(1, icon.width() // 64)  # shrink 1024px source to ~64px
                self._icon = icon.subsample(factor, factor)
                self.iconphoto(True, self._icon)
            except Exception:  # noqa: BLE001
                pass

    def _build_sidebar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=COL_SIDEBAR, corner_radius=0, width=248)
        bar.grid(row=0, column=0, sticky="nsew")
        bar.grid_propagate(False)

        brand = ctk.CTkFrame(bar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(24, 8))
        logo = ASSETS / "logo.png"
        if logo.is_file():
            img = ctk.CTkImage(Image.open(logo), size=(46, 46))
            self._logo_img = img
            ctk.CTkLabel(brand, image=img, text="").pack(side="left")
        text = ctk.CTkFrame(brand, fg_color="transparent")
        text.pack(side="left", padx=12)
        ctk.CTkLabel(text, text=APP_NAME, text_color=COL_TEXT, font=f(18, "bold")).pack(anchor="w")
        ctk.CTkLabel(text, text="PDF toolkit", text_color=COL_ACCENT_2, font=f(12)).pack(anchor="w")

        ctk.CTkFrame(bar, fg_color=COL_STROKE, height=1).pack(fill="x", padx=20, pady=(12, 12))

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for name, _ in self.PAGES:
            b = ctk.CTkButton(bar, text="   " + name, anchor="w", height=44,
                              corner_radius=12, fg_color="transparent",
                              hover_color=COL_CARD, text_color=COL_MUTED,
                              font=f(15), command=lambda n=name: self.select(n))
            b.pack(fill="x", padx=14, pady=4)
            self.nav_buttons[name] = b

        footer = ctk.CTkFrame(bar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=20, pady=18)
        ctk.CTkLabel(footer, text=f"v{APP_VERSION}  \u00b7  offline & local",
                     text_color=COL_MUTED, font=f(11)).pack(anchor="w")

    def select(self, name: str) -> None:
        self.pages[name].ensure_built()
        self.pages[name].tkraise()
        for n, b in self.nav_buttons.items():
            if n == name:
                b.configure(fg_color=COL_ACCENT, text_color="#06110A")
            else:
                b.configure(fg_color="transparent", text_color=COL_MUTED)


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
