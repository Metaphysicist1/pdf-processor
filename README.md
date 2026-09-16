<div align="center">

<img src="assets/logo.png" alt="PDF Studio logo" width="120" />

# PDF Studio

**Offline desktop toolkit for everyday PDF work — plus a scriptable CLI.**

Merge · Compress · Strip metadata · Remove pages · PDF → carousel images · Images → PDF

</div>

---

Everything runs **locally** — documents never leave your machine.

| | |
| --- | --- |
| Desktop app | Matrix-inspired dark UI, native file dialogs, progress bar |
| CLI | `pdfstudio.carousel` for Instagram / LinkedIn image workflows |

<div align="center">
<img src="assets/screenshot.png" alt="PDF Studio desktop app" width="820" />
</div>

## Features

| Tool | What it does |
| --- | --- |
| **Merge** | Combine several PDFs into one (reorder before export). |
| **Compress** | Shrink a PDF by recompressing images + content streams. |
| **Strip Metadata** | Remove Author/Creator/Producer/title/timestamps via a full pikepdf rewrite (non-reversible). |
| **Remove Pages** | Delete specific pages (e.g. `2, 5, 9`). |
| **PDF → Images** | Crisp carousel images for Instagram (4:5, 1:1, 9:16), `pad` / `cover`, sRGB, PNG/JPG. |
| **Images → PDF** | Combine images into one PDF for a LinkedIn document post. |

## For everyone (no tech skills)

**Windows — just download and double-click**

1. Open the repo’s [**Releases**](https://github.com/Metaphysicist1/pdf-processor/releases) page.
2. Download **`PDFStudio.exe`**.
3. Double-click it. That’s it — no Python, no install, no terminal.

> First launch: Windows may show “Windows protected your PC” (SmartScreen) because the
> app isn’t code-signed. Click **More info** → **Run anyway**. The app is offline and
> doesn’t send your files anywhere.

You can also download a build from the latest successful
[**Actions → Build Windows EXE**](https://github.com/Metaphysicist1/pdf-processor/actions)
run (Artifacts → `PDFStudio-windows`).

**How we verify Windows works:** GitHub builds the `.exe` on a real Windows machine
(Actions). You (or a friend) then open `PDFStudio.exe` once on a PC and try Merge /
Compress. We can’t run a Windows GUI from Linux — the Actions build + a quick
double-click test on a Windows PC is the check.

## Quick start (developers)

Requires **Python 3.10+**.

### Linux / macOS

```bash
./scripts/install.sh    # creates .venv + installs deps
./run.sh                # starts the desktop app
```

Optional — pin to your app menu:

```bash
./scripts/install_desktop_linux.sh
```

### Windows (from source)

1. Install [Python 3.10+](https://www.python.org/downloads/windows/) (tick **Add Python to PATH**).
2. Double-click **`scripts\install.bat`**
3. Double-click **`run.bat`** (project root)

### Manual (any OS)

```bash
python -m venv .venv
# Linux/macOS:  source .venv/bin/activate
# Windows:      .venv\Scripts\activate
pip install -r requirements.txt
python run.py
# or:  python -m pdfstudio
```

## Build a standalone app

| OS | How | Output |
| --- | --- | --- |
| Windows (CI) | Push a tag `v1.0.0` **or** run **Actions → Build Windows EXE → Run workflow** | `PDFStudio.exe` artifact / Release |
| Windows (local) | Double-click `scripts\build_windows.bat` | `dist\PDFStudio.exe` |
| Linux | `./scripts/build_linux.sh` | `dist/PDFStudio` |

PyInstaller does **not** cross-compile — CI builds Windows on `windows-latest`.  
After building on Linux, re-run `./scripts/install_desktop_linux.sh` to point the menu entry at the binary.

## Command-line (carousel)

```bash
# after install / with venv active
python -m pdfstudio.carousel split input.pdf -o slides/
python -m pdfstudio.carousel split input.pdf -o slides/ --size 1x1 --fit cover --format jpg
python -m pdfstudio.carousel build slides/ -o carousel.pdf

# same via shim
python scripts/carousel_cli.py split input.pdf -o slides/
```

| Flag | Values | Default | Notes |
| --- | --- | --- | --- |
| `--size` | `4x5`, `1x1`, `9x16` | `4x5` | 1080×1350 / 1080×1080 / 1080×1920 |
| `--fit` | `pad`, `cover` | `pad` | letterbox vs crop-to-fill |
| `--bg` | hex color | auto | pad background; defaults to sampled corner color |
| `--format` | `png`, `jpg` | `png` | jpg is quality 95, no chroma subsampling |
| `--max-slides` | integer | all | Instagram caps carousels at 20 |

## Project layout

```
pdf-processor/
├── run.py / run.sh / run.bat   # one-click launchers
├── requirements.txt
├── assets/                     # logo, screenshots, desktop template
├── pdfstudio/                  # application package
│   ├── app.py                  # desktop UI
│   ├── engine.py               # merge / compress / strip / remove / split / build
│   ├── carousel.py             # PDF <-> image CLI
│   └── dialogs.py              # native file dialogs
├── examples/                   # tiny standalone pypdf scripts
├── scripts/                    # install, run, build, desktop helpers
└── packaging/
    └── PDFStudio.spec          # PyInstaller config
```

## Dependencies

[`pymupdf`](https://pymupdf.readthedocs.io) · [`Pillow`](https://python-pillow.org) ·
[`pypdf`](https://pypdf.readthedocs.io) · [`pikepdf`](https://pikepdf.readthedocs.io) ·
[`customtkinter`](https://customtkinter.tomschimansky.com)

No poppler, ImageMagick, ExifTool, or other system binaries required.  
On Linux, optional `zenity` gives the native GTK file picker (falls back otherwise).

## Notes

- Offline only — no network calls, no telemetry.
- Metadata stripping fully rewrites the PDF (old values not recoverable).
- `split` writes zero-padded names (`slide_01.png`); `build` uses natural sort.
