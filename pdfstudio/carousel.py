#!/usr/bin/env python3
"""carousel.py - convert between PDFs and social carousel images.

Two commands:

    python carousel.py split <input.pdf> -o <outdir>
        PDF pages -> numbered images ready for an Instagram carousel.

    python carousel.py build <indir> -o <output.pdf>
        Folder of images -> single PDF ready for a LinkedIn document post.

Dependencies (see requirements.txt):
    - PyMuPDF (pymupdf)  : PDF rasterization. `import fitz`
    - Pillow (PIL)       : all image operations.
No poppler / ImageMagick / pdf2image required.
"""

from __future__ import annotations

import argparse
import io
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image, ImageCms

logger = logging.getLogger("carousel")

# --- Constants -------------------------------------------------------------

SIZES: dict[str, tuple[int, int]] = {
    "4x5": (1080, 1350),
    "1x1": (1080, 1080),
    "9x16": (1080, 1920),
}

DEFAULT_SIZE = "4x5"
INSTAGRAM_MAX_SLIDES = 20
# Render at >= this multiple of the target width before downsampling.
RENDER_SCALE = 3
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


# --- Shared helpers --------------------------------------------------------


def die(message: str) -> "NoReturn":  # type: ignore[name-defined]
    """Fail loudly with a clear message and a non-zero exit code."""
    logger.error(message)
    sys.exit(1)


def parse_hex_color(value: str) -> tuple[int, int, int]:
    """Parse a #rrggbb / rrggbb / #rgb hex string into an RGB tuple."""
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
        raise argparse.ArgumentTypeError(f"invalid hex color: {value!r}")
    return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# --- sRGB conversion -------------------------------------------------------

_SRGB_PROFILE = ImageCms.createProfile("sRGB")


def to_srgb(image: Image.Image) -> Image.Image:
    """Return an RGB image in the sRGB color space.

    Handles embedded ICC profiles (converting them to sRGB) and CMYK sources
    explicitly, so colors are not silently shifted on the way out.
    """
    icc = image.info.get("icc_profile")
    if icc:
        try:
            src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            converted = ImageCms.profileToProfile(
                image, src_profile, _SRGB_PROFILE, outputMode="RGB"
            )
            if converted is not None:
                return converted
        except Exception as exc:  # noqa: BLE001 - fall back gracefully
            logger.warning("ICC->sRGB conversion failed (%s); using naive convert", exc)

    if image.mode == "CMYK":
        # No embedded profile: naive but explicit CMYK->RGB.
        return image.convert("RGB")
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


# --- split -----------------------------------------------------------------


def sample_corner_modal_color(image: Image.Image, box: int = 20) -> tuple[int, int, int]:
    """Sample the modal color across the image's four 20x20 corner regions."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    box = min(box, w, h)
    regions = [
        (0, 0, box, box),
        (w - box, 0, w, box),
        (0, h - box, box, h),
        (w - box, h - box, w, h),
    ]
    counter: Counter[tuple[int, int, int]] = Counter()
    for region in regions:
        for pixel in rgb.crop(region).getdata():
            counter[pixel] += 1
    return counter.most_common(1)[0][0]


def fit_pad(
    src: Image.Image, target: tuple[int, int], bg: tuple[int, int, int]
) -> Image.Image:
    """Letterbox `src` into `target` with no content loss."""
    tw, th = target
    scale = min(tw / src.width, th / src.height)
    new_w = max(1, round(src.width * scale))
    new_h = max(1, round(src.height * scale))
    resized = src.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", target, bg)
    canvas.paste(resized, ((tw - new_w) // 2, (th - new_h) // 2))
    return canvas


def fit_cover(src: Image.Image, target: tuple[int, int]) -> Image.Image:
    """Crop-to-fill `src` into `target`, center-anchored."""
    tw, th = target
    scale = max(tw / src.width, th / src.height)
    new_w = max(tw, round(src.width * scale))
    new_h = max(th, round(src.height * scale))
    resized = src.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def render_page_hires(page: "fitz.Page", target: tuple[int, int]) -> Image.Image:
    """Rasterize a PDF page at >= RENDER_SCALE x the target width.

    Never upscales a low-res render: the zoom is capped so we do not render
    the page at more pixels than it naturally provides at 72 DPI baseline
    beyond what LANCZOS downsampling needs.
    """
    tw, _ = target
    rect = page.rect
    if rect.width <= 0 or rect.height <= 0:
        raise ValueError("page has zero area")

    desired_px = RENDER_SCALE * tw
    zoom = desired_px / rect.width
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    mode = "RGB" if pix.n < 4 else "CMYK"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    if pix.xres and pix.yres:
        img.info.setdefault("dpi", (pix.xres, pix.yres))
    return img


def cmd_split(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    if not input_path.is_file():
        die(f"input PDF not found: {input_path}")

    target = SIZES[args.size]
    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(input_path)
    except Exception as exc:  # noqa: BLE001
        die(f"could not open PDF {input_path}: {exc}")

    page_count = doc.page_count
    if page_count == 0:
        die(f"PDF has zero pages: {input_path}")

    limit = page_count
    if args.max_slides is not None:
        if args.max_slides < 1:
            die("--max-slides must be >= 1")
        limit = min(limit, args.max_slides)
    elif page_count > INSTAGRAM_MAX_SLIDES:
        logger.warning(
            "PDF has %d pages; Instagram caps carousels at %d slides. "
            "Writing all %d anyway (use --max-slides to truncate).",
            page_count,
            INSTAGRAM_MAX_SLIDES,
            page_count,
        )

    pad_width = max(2, len(str(limit)))
    fmt = args.format
    ext = "jpg" if fmt == "jpg" else "png"

    for index in range(limit):
        page = doc.load_page(index)
        try:
            hires = render_page_hires(page, target)
        except ValueError as exc:
            die(f"page {index + 1}: {exc}")

        src_w, src_h = hires.size
        hires = to_srgb(hires)

        if args.fit == "cover":
            result = fit_cover(hires, target)
        else:
            if args.bg is not None:
                bg = args.bg
            else:
                bg = sample_corner_modal_color(hires)
            result = fit_pad(hires, target, bg)

        name = f"slide_{index + 1:0{pad_width}d}.{ext}"
        out_path = outdir / name
        if fmt == "jpg":
            result.save(out_path, "JPEG", quality=95, subsampling=0)
        else:
            result.save(out_path, "PNG")

        print(
            f"[{index + 1:>{pad_width}}/{limit}] "
            f"src {src_w}x{src_h} -> out {result.width}x{result.height} "
            f"fit={args.fit} -> {name}"
        )

    doc.close()


# --- build -----------------------------------------------------------------

_NAT_RE = re.compile(r"(\d+)")


def natural_key(path: Path) -> list:
    """Natural sort key so slide_2 sorts before slide_10."""
    parts = _NAT_RE.split(path.name.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def flatten_to_rgb(image: Image.Image) -> Image.Image:
    """Composite any alpha channel against white; PDFs have no alpha."""
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def cmd_build(args: argparse.Namespace) -> None:
    indir = Path(args.input)
    if not indir.is_dir():
        die(f"input directory not found: {indir}")

    images = sorted(
        (p for p in indir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS),
        key=natural_key,
    )
    if not images:
        die(f"no .png/.jpg/.jpeg images found in {indir}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frames: list[Image.Image] = []
    for path in images:
        try:
            with Image.open(path) as im:
                frames.append(flatten_to_rgb(im.copy()))
        except Exception as exc:  # noqa: BLE001
            die(f"could not read image {path}: {exc}")
        logger.info("added %s", path.name)

    first, rest = frames[0], frames[1:]
    first.save(
        output_path,
        "PDF",
        save_all=True,
        append_images=rest,
        resolution=72.0,
    )

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"wrote {len(frames)} pages -> {output_path} ({size_mb:.2f} MB)")


# --- CLI -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="carousel.py",
        description="Convert between PDFs and social carousel images.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_split = sub.add_parser("split", help="PDF pages -> carousel images")
    p_split.add_argument("input", help="input PDF path")
    p_split.add_argument("-o", "--output", required=True, help="output directory")
    p_split.add_argument(
        "--size",
        choices=sorted(SIZES),
        default=DEFAULT_SIZE,
        help="target size (default: 4x5 -> 1080x1350)",
    )
    p_split.add_argument(
        "--fit",
        choices=["pad", "cover"],
        default="pad",
        help="pad=letterbox (default), cover=crop-to-fill",
    )
    p_split.add_argument(
        "--bg",
        type=parse_hex_color,
        default=None,
        help="pad background hex color; default samples page corners",
    )
    p_split.add_argument(
        "--format",
        choices=["png", "jpg"],
        default="png",
        help="output image format (default: png)",
    )
    p_split.add_argument(
        "--max-slides",
        type=int,
        default=None,
        help="truncate to first N pages",
    )
    p_split.set_defaults(func=cmd_split)

    p_build = sub.add_parser("build", help="carousel images -> single PDF")
    p_build.add_argument("input", help="input directory of images")
    p_build.add_argument("-o", "--output", required=True, help="output PDF path")
    p_build.set_defaults(func=cmd_build)

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
