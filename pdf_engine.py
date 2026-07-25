#!/usr/bin/env python3
"""pdf_engine.py - the shared PDF/image operations behind the CLI and the app.

This module contains pure, UI-agnostic functions. Each takes an optional
``progress`` callback ``Callable[[float, str], None]`` (fraction 0..1, message)
so a GUI can render a progress bar, and raises ``EngineError`` on any failure
with a clear, user-facing message.

Dependencies (see requirements.txt):
    - pypdf     : merge / compress / remove pages
    - PyMuPDF   : PDF rasterization (via carousel.py)
    - Pillow    : image operations (via carousel.py)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

from pypdf import PdfReader, PdfWriter

import carousel

logger = logging.getLogger("pdf_engine")

Progress = Callable[[float, str], None]


class EngineError(Exception):
    """Raised for any user-facing failure so the UI can show a clean message."""


def _report(progress: Optional[Progress], fraction: float, message: str) -> None:
    if progress is not None:
        progress(max(0.0, min(1.0, fraction)), message)


def _mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


# --- Merge -----------------------------------------------------------------


def merge_pdfs(
    inputs: Sequence[str | Path],
    output: str | Path,
    progress: Optional[Progress] = None,
) -> dict:
    """Merge multiple PDFs into one, in the given order."""
    paths = [Path(p) for p in inputs]
    if len(paths) < 2:
        raise EngineError("Select at least two PDFs to merge.")
    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise EngineError("File not found: " + ", ".join(p.name for p in missing))

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    writer = PdfWriter()
    total_pages = 0
    try:
        for i, path in enumerate(paths):
            _report(progress, i / len(paths), f"Adding {path.name}")
            reader = PdfReader(str(path))
            for page in reader.pages:
                writer.add_page(page)
                total_pages += 1
        _report(progress, 0.95, "Writing merged PDF")
        with open(output, "wb") as fh:
            writer.write(fh)
    except EngineError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise EngineError(f"Could not merge PDFs: {exc}") from exc
    finally:
        writer.close()

    _report(progress, 1.0, "Done")
    return {"pages": total_pages, "files": len(paths), "output": str(output), "mb": _mb(output)}


# --- Compress --------------------------------------------------------------


def compress_pdf(
    input_path: str | Path,
    output_path: str | Path,
    quality: int = 65,
    progress: Optional[Progress] = None,
) -> dict:
    """Recompress content streams (lossless) and images (lossy) in a PDF."""
    input_path = Path(input_path)
    if not input_path.is_file():
        raise EngineError(f"Input PDF not found: {input_path}")
    if not 1 <= quality <= 100:
        raise EngineError("Image quality must be between 1 and 100.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        writer = PdfWriter(clone_from=str(input_path))
        pages = list(writer.pages)
        total = len(pages) or 1
        for i, page in enumerate(pages):
            _report(progress, i / total, f"Compressing page {i + 1}/{total}")
            try:
                page.compress_content_streams(level=9)
            except Exception as exc:  # noqa: BLE001
                logger.warning("content stream compression failed on page %d: %s", i + 1, exc)
            for img in page.images:
                try:
                    img.replace(img.image, quality=quality)
                except Exception:  # noqa: BLE001 - unsupported image format, skip safely
                    pass
        _report(progress, 0.97, "Writing compressed PDF")
        with open(output_path, "wb") as fh:
            writer.write(fh)
    except EngineError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise EngineError(f"Could not compress PDF: {exc}") from exc

    original = _mb(input_path)
    new = _mb(output_path)
    saved = (1 - new / original) * 100 if original else 0.0
    _report(progress, 1.0, "Done")
    return {
        "original_mb": original,
        "new_mb": new,
        "saved_pct": saved,
        "output": str(output_path),
    }


# --- Remove pages ----------------------------------------------------------


def remove_pages(
    input_path: str | Path,
    output_path: str | Path,
    pages_to_remove: Iterable[int],
    progress: Optional[Progress] = None,
) -> dict:
    """Remove 1-based page numbers from a PDF, keeping the rest in order."""
    input_path = Path(input_path)
    if not input_path.is_file():
        raise EngineError(f"Input PDF not found: {input_path}")

    remove_set = {int(p) for p in pages_to_remove}
    if not remove_set:
        raise EngineError("No pages specified to remove.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        reader = PdfReader(str(input_path))
        total = len(reader.pages)
        if total == 0:
            raise EngineError("PDF has zero pages.")
        invalid = sorted(p for p in remove_set if p < 1 or p > total)
        if invalid:
            raise EngineError(
                f"Page(s) {', '.join(map(str, invalid))} out of range (document has {total})."
            )
        if len(remove_set) >= total:
            raise EngineError("Refusing to remove every page.")

        writer = PdfWriter()
        kept = 0
        for index, page in enumerate(reader.pages):
            _report(progress, index / total, f"Processing page {index + 1}/{total}")
            if (index + 1) not in remove_set:
                writer.add_page(page)
                kept += 1
        _report(progress, 0.97, "Writing PDF")
        with open(output_path, "wb") as fh:
            writer.write(fh)
    except EngineError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise EngineError(f"Could not remove pages: {exc}") from exc

    _report(progress, 1.0, "Done")
    return {
        "removed": sorted(remove_set),
        "kept": kept,
        "output": str(output_path),
        "mb": _mb(output_path),
    }


# --- Carousel split (PDF -> images) ---------------------------------------


def split_pdf_to_images(
    input_path: str | Path,
    outdir: str | Path,
    size: str = "4x5",
    fit: str = "pad",
    bg: Optional[tuple[int, int, int]] = None,
    fmt: str = "png",
    max_slides: Optional[int] = None,
    progress: Optional[Progress] = None,
) -> dict:
    """Rasterize each PDF page into a numbered carousel image via carousel.py."""
    input_path = Path(input_path)
    if not input_path.is_file():
        raise EngineError(f"Input PDF not found: {input_path}")
    if size not in carousel.SIZES:
        raise EngineError(f"Unknown size {size!r}. Choose from {sorted(carousel.SIZES)}.")
    if fit not in ("pad", "cover"):
        raise EngineError("fit must be 'pad' or 'cover'.")
    if fmt not in ("png", "jpg"):
        raise EngineError("format must be 'png' or 'jpg'.")

    target = carousel.SIZES[size]
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        import fitz  # local import; PyMuPDF

        doc = fitz.open(str(input_path))
    except Exception as exc:  # noqa: BLE001
        raise EngineError(f"Could not open PDF: {exc}") from exc

    page_count = doc.page_count
    if page_count == 0:
        doc.close()
        raise EngineError("PDF has zero pages.")

    limit = page_count
    warning: Optional[str] = None
    if max_slides is not None:
        if max_slides < 1:
            doc.close()
            raise EngineError("max slides must be >= 1.")
        limit = min(limit, max_slides)
    elif page_count > carousel.INSTAGRAM_MAX_SLIDES:
        warning = (
            f"PDF has {page_count} pages; Instagram caps carousels at "
            f"{carousel.INSTAGRAM_MAX_SLIDES}. Exported all {page_count} anyway."
        )

    pad_width = max(2, len(str(limit)))
    ext = "jpg" if fmt == "jpg" else "png"
    written: list[str] = []

    try:
        for index in range(limit):
            _report(progress, index / limit, f"Rendering page {index + 1}/{limit}")
            page = doc.load_page(index)
            hires = carousel.render_page_hires(page, target)
            hires = carousel.to_srgb(hires)
            if fit == "cover":
                result = carousel.fit_cover(hires, target)
            else:
                fill = bg if bg is not None else carousel.sample_corner_modal_color(hires)
                result = carousel.fit_pad(hires, target, fill)
            name = f"slide_{index + 1:0{pad_width}d}.{ext}"
            out_path = outdir / name
            if fmt == "jpg":
                result.save(out_path, "JPEG", quality=95, subsampling=0)
            else:
                result.save(out_path, "PNG")
            written.append(str(out_path))
    except Exception as exc:  # noqa: BLE001
        raise EngineError(f"Could not render page: {exc}") from exc
    finally:
        doc.close()

    _report(progress, 1.0, "Done")
    return {
        "count": len(written),
        "files": written,
        "size": f"{target[0]}x{target[1]}",
        "fit": fit,
        "warning": warning,
        "outdir": str(outdir),
    }


# --- Carousel build (images -> PDF) ---------------------------------------


def build_pdf_from_images(
    inputs: Sequence[str | Path] | str | Path,
    output: str | Path,
    progress: Optional[Progress] = None,
) -> dict:
    """Combine images into a single multi-page PDF (LinkedIn document post).

    ``inputs`` may be a directory (all images inside, natural-sorted) or an
    explicit, already-ordered sequence of image paths.
    """
    from PIL import Image

    if isinstance(inputs, (str, Path)) and Path(inputs).is_dir():
        indir = Path(inputs)
        image_paths = sorted(
            (p for p in indir.iterdir() if p.suffix.lower() in carousel.IMAGE_EXTENSIONS),
            key=carousel.natural_key,
        )
    else:
        seq = [inputs] if isinstance(inputs, (str, Path)) else list(inputs)
        image_paths = [Path(p) for p in seq]

    if not image_paths:
        raise EngineError("No .png/.jpg/.jpeg images found.")
    missing = [p for p in image_paths if not p.is_file()]
    if missing:
        raise EngineError("Image not found: " + ", ".join(p.name for p in missing))

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    frames = []
    try:
        total = len(image_paths)
        for i, path in enumerate(image_paths):
            _report(progress, i / total, f"Adding {path.name}")
            with Image.open(path) as im:
                frames.append(carousel.flatten_to_rgb(im.copy()))
        _report(progress, 0.95, "Writing PDF")
        frames[0].save(
            output,
            "PDF",
            save_all=True,
            append_images=frames[1:],
            resolution=72.0,
        )
    except Exception as exc:  # noqa: BLE001
        raise EngineError(f"Could not build PDF: {exc}") from exc

    _report(progress, 1.0, "Done")
    return {"pages": len(frames), "output": str(output), "mb": _mb(output)}


# --- Small helpers used by the UI -----------------------------------------


def pdf_page_count(input_path: str | Path) -> int:
    """Return the number of pages in a PDF, or raise EngineError."""
    path = Path(input_path)
    if not path.is_file():
        raise EngineError(f"Input PDF not found: {path}")
    try:
        return len(PdfReader(str(path)).pages)
    except Exception as exc:  # noqa: BLE001
        raise EngineError(f"Could not read PDF: {exc}") from exc
