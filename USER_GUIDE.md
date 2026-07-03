# DXFvec User Guide

> **Version 2.0** — Industry-grade image vectorization and DXF conversion.

---

## Table of Contents

1. [What is DXFvec](#1-what-is-dxfvec)
2. [System Requirements](#2-system-requirements)
3. [Installation](#3-installation)
4. [Local Development Setup](#4-local-development-setup)
   - [Prerequisites](#prerequisites)
   - [Clone & Install](#clone--install)
   - [Environment Configuration](#environment-configuration)
   - [Verify Setup](#verify-setup)
   - [Running Locally](#running-locally)
   - [IDE Setup](#ide-setup)
   - [Common Development Tasks](#common-development-tasks)
5. [Quick Start](#5-quick-start)
6. [CLI Reference](#6-cli-reference)
   - [Global Options](#global-options)
   - [dxfvec convert](#dxfvec-convert)
   - [dxfvec batch](#dxfvec-batch)
   - [dxfvec modify](#dxfvec-modify)
   - [dxfvec enhance](#dxfvec-enhance)
   - [dxfvec engines / presets / providers / info](#informational-commands)
7. [Engines](#7-engines)
   - [Classic Engine](#classic-engine)
   - [Advanced Engine](#advanced-engine)
   - [Cloud AI Engines](#cloud-ai-engines-byok)
8. [Presets](#8-presets)
9. [Calibration & Units](#9-calibration--units)
10. [DXF Output Details](#10-dxf-output-details)
    - [Layer Semantics](#layer-semantics)
    - [DXF Versions](#dxf-versions)
    - [Arc & Circle Detection](#arc--circle-detection)
11. [QA Reports](#11-qa-reports)
12. [Web UI](#12-web-ui)
    - [Starting the Server](#starting-the-server)
    - [Single Image Upload](#single-image-upload)
    - [Batch Upload](#batch-upload)
    - [DXF Viewer](#dxf-viewer)
    - [File Gallery](#file-gallery)
13. [REST API](#13-rest-api)
14. [LLM Vision Pipeline](#14-llm-vision-pipeline)
    - [Setup](#setup)
    - [Single LLM Call](#single-llm-call)
    - [CrewAI Multi-Agent](#crewai-multi-agent)
15. [Python API](#15-python-api)
16. [Docker Deployment](#16-docker-deployment)
17. [Environment Variables](#17-environment-variables)
18. [Troubleshooting](#18-troubleshooting)
19. [FAQ](#19-faq)

---

## 1. What is DXFvec

DXFvec converts raster images (PNG, JPG, WEBP, BMP, TIFF) into CAD/CNC-ready DXF vector files. It is **100% free** and runs entirely locally — no API keys required for the core engines.

**Key capabilities:**
- Three vectorization engines: Classic (OpenCV), Advanced (VTracer), Cloud AI (BYOK)
- Native ARC/CIRCLE entities in DXF output (not polyline approximations)
- CNC layer semantics: CUT (red), ENGRAVE (blue), BEND (blue dashed), DIM (green)
- Real-world calibration (pixel-to-mm/cm/in mapping)
- DXF version selection (R12, R2010, R2018)
- Automatic QA reports with DXF audit validation
- Web UI with drag-and-drop upload, canvas viewer, and batch processing
- CLI for scripting, automation, and CI/CD integration

---

## 2. System Requirements

| Requirement | Minimum |
|-------------|---------|
| Python | 3.10+ |
| RAM | 2 GB (4 GB recommended for large images) |
| Disk | 500 MB for installation |
| OS | Windows 10+, macOS 11+, Ubuntu 20.04+ |

**Optional:**
- GPU: Not required. All processing is CPU-based.
- Docker: For containerized deployment
- API keys: Only needed for Cloud AI engines or LLM vision pipeline

---

## 3. Installation

### Option A: pipx (recommended for CLI-only)

```bash
pipx install dxfvec
dxfvec engines   # verify
```

### Option B: Virtual environment (recommended for development)

```bash
# Create and activate venv
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install with all features
pip install -e ".[web,crew]"
```

### Option C: Docker

```bash
docker compose up -d
# Web UI at http://localhost:5000
```

### Optional extras

| Extra | Command | What it adds |
|-------|---------|--------------|
| `web` | `pip install -e ".[web]"` | Flask web UI, Gunicorn |
| `crew` | `pip install -e ".[crew]"` | LLM vision pipeline (LiteLLM, CrewAI) |
| `dev` | `pip install -e ".[dev]"` | Ruff, mypy, pytest |
| `cloud` | `pip install -e ".[cloud]"` | BYOK cloud API wrappers |

### Verify installation

```bash
dxfvec engines
dxfvec presets
dxfvec providers
dxfvec info
```

---

## 4. Local Development Setup

Step-by-step guide to get DXFvec running from source on your local machine.

### Prerequisites

**Required:**
- **Python 3.10+** (3.10, 3.11, or 3.12 confirmed working)
- **Git**
- **pip** (bundled with Python 3.10+)

**Optional but recommended:**
- **pyenv** (Python version management) — avoids system Python conflicts
- **pipx** (global CLI installs)
- **Docker Desktop** (for containerized testing)

**OS-specific system libraries (Linux only):**

```bash
# Ubuntu / Debian — required before install
sudo apt update && sudo apt install -y libglib2.0-0 libgomp1

# Fedora / RHEL
sudo dnf install glib2 libgomp
```

Windows and macOS need no extra system libraries.

### Clone & Install

**1. Clone the repository:**

```bash
git clone https://github.com/Warriorlegacy/dxfvec.git
cd dxfvec
```

**2. Create and activate a virtual environment:**

```bash
# Create venv
python -m venv .venv

# Activate — Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Activate — Windows (cmd):
.venv\Scripts\activate.bat

# Activate — macOS / Linux:
source .venv/bin/activate
```

> **PowerShell users:** If you get a "running scripts is disabled" error:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

**3. Install in editable mode with all extras:**

```bash
# Full install (CLI + web UI + LLM pipeline + dev tools)
pip install -e ".[web,crew,dev]"
```

Or install selectively:

```bash
# CLI only (no web UI, no LLM)
pip install -e .

# CLI + web UI
pip install -e ".[web]"

# CLI + LLM vision pipeline
pip install -e ".[crew]"

# Everything including dev tools
pip install -e ".[web,crew,dev]"
```

**4. Verify the install:**

```bash
dxfvec info
dxfvec engines
dxfvec presets
```

You should see Python version, dependency versions, and the list of engines/presets.

### Environment Configuration

**1. Copy the example env file:**

```bash
cp .env.example .env
```

**2. Edit `.env` with your keys (only what you need):**

```ini
# Web server (defaults work for local dev)
PORT=5000
FLASK_DEBUG=1

# LLM providers — uncomment at least one if using --provider
# GEMINI_API_KEY=your-key-here
# OPENAI_API_KEY=your-key-here

# Cloud engines (optional)
# DXVEC_VECTORIZER_AI_API_ID=your-id
# DXVEC_VECTORIZER_AI_API_SECRET=your-secret
```

**3. `.env` is loaded automatically** by:
- Flask (web UI)
- LiteLLM (LLM pipeline)
- The CLI reads it on startup

> **Security:** `.env` is in `.gitignore` and will NOT be committed. Never paste real API keys into chat or commit messages.

### Verify Setup

Run these commands to confirm everything works:

```bash
# 1. Show runtime info
dxfvec info

# 2. Check engines are available
dxfvec engines

# 3. List presets
dxfvec presets

# 4. Check cloud provider status
dxfvec providers

# 5. Run the full test suite
python -m pytest tests/ -v --timeout=60

# 6. Run linting
ruff check src/ tests/

# 7. Run type checking
mypy src/ --ignore-missing-imports
```

Expected output:
- `dxfvec info` shows all dependencies with version numbers
- `ruff check` passes with 0 errors
- `pytest` shows 153 tests passing

### Running Locally

**Option A: Web UI (development server)**

```bash
python -m dxfvec.web
# Open http://localhost:5000
```

Flask runs with `FLASK_DEBUG=1` — auto-reloads on code changes.

**Option B: CLI**

```bash
# Convert a test image
dxfvec convert path/to/image.png --engine classic --mode lines -o ./output/

# Batch convert
dxfvec batch ./test_images/ --engine advanced
```

**Option C: Python API**

```python
# From a Python shell or script
from pathlib import Path
from dxfvec import ClassicEngine

engine = ClassicEngine()
result = engine.convert(
    image_path=Path("test.png"),
    output_dir=Path("./output"),
    config={
        "dxf_mode": "lines",
        "dxf_version": "R2010",
        "trace_mode": "outline",
        "detect_arcs": True,
        "cnc_layers": True,
        "units": "mm",
    },
)
print(result["dxf"])
```

**Option D: Docker (local container)**

```bash
docker compose up -d
# Web UI at http://localhost:5000
docker compose logs -f   # watch logs
docker compose down      # stop
```

### IDE Setup

**VS Code (recommended):**

1. Install the Python extension
2. Open the project folder
3. Select the `.venv` interpreter (Ctrl+Shift+P → "Python: Select Interpreter")
4. Recommended extensions:
   - Ruff (linting/formatting)
   - Python (language support)
   - Pylance (type checking)

**PyCharm:**

1. Open the project root
2. Set interpreter to `.venv/Scripts/python.exe` (Windows) or `.venv/bin/python` (macOS/Linux)
3. Mark `src/` as Sources Root

### Common Development Tasks

**Run tests:**

```bash
# Full suite
python -m pytest tests/ -v --timeout=60

# Single test file
python -m pytest tests/test_path_model.py -v

# Single test
python -m pytest tests/test_path_model.py::test_vec2_operations -v

# With coverage
pip install pytest-cov
python -m pytest tests/ --cov=dxfvec --cov-report=html
```

**Lint and format:**

```bash
# Check for lint errors
ruff check src/ tests/

# Auto-fix lint errors
ruff check src/ tests/ --fix

# Format code
ruff format src/ tests/
```

**Type check:**

```bash
mypy src/ --ignore-missing-imports
```

**Test a single image through the full pipeline:**

```bash
# Classic engine
dxfvec convert test.png --debug -o ./test_output/

# Advanced engine with arcs
dxfvec convert test.png --engine advanced --detect-arcs --tolerance-mm 0.1 --debug

# With calibration
dxfvec convert test.png --scale 64px=20mm --dxf-version R2018 --debug
```

**Generate a test DXF programmatically:**

```python
from pathlib import Path
from dxfvec import PathModel, polyline_to_path, circle_to_path, write_dxf

model = PathModel()

# Square
model.paths.append(polyline_to_path(
    [(0, 0), (50, 0), (50, 50), (0, 50)],
    layer="CUT", closed=True,
))

# Circle
model.paths.append(circle_to_path(25, 25, 10, layer="ENGRAVE", n_points=32))

write_dxf(model, Path("test_output.dxf"), dxf_version="R2010", units="mm")
```

**Reset the development environment:**

```bash
# Nuclear option — rebuild venv from scratch
deactivate
rm -rf .venv/
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[web,crew,dev]"
cp .env.example .env
# Edit .env as needed
```

**Update dependencies:**

```bash
pip install -e ".[web,crew,dev]" --upgrade
```

---

## 5. Quick Start

### Convert a single image (simplest)

```bash
dxfvec convert drawing.png
```

This uses the Classic engine and outputs to `./output/`.

### Convert with higher quality

```bash
dxfvec convert drawing.png --engine advanced --detect-arcs --tolerance-mm 0.1
```

### Convert with real-world dimensions

```bash
# Tell DXFvec that 64 pixels = 20 millimeters
dxfvec convert drawing.png --scale 64px=20mm --dxf-version R2018
```

### Batch convert a folder

```bash
dxfvec batch ./drawings/ --format zip --engine advanced
```

### Use a preset for specific use cases

```bash
dxfvec convert logo.png --preset logo_engrave
dxfvec convert stencil.png --preset laser_stencil
dxfvec convert blueprint.png --preset technical_drawing
```

---

## 6. CLI Reference

### Global Options

```
dxfvec [OPTIONS] COMMAND [ARGS]

Options:
  --version    Show version
  -v, --verbose   Increase verbosity (repeatable: -v, -vv, -vvv)
  -q, --quiet     Suppress non-essential output
```

### `dxfvec convert`

Convert a single raster image to DXF.

```
dxfvec convert IMAGE [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `IMAGE` | Path to input image (PNG, JPG, WEBP, BMP, TIFF) |

**Engine options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--engine, -e` | `classic` | Engine: `classic`, `advanced`, `cloud:vectorizer_ai`, `cloud:dxfai` |
| `--mode, -m` | `lines` | DXF mode: `lines`, `hatch`, `faces` |
| `--trace-mode` | `outline` | Trace mode: `outline` or `centerline` |
| `--detect-arcs / --no-detect-arcs` | enabled | Detect arcs/circles → native DXF entities |
| `--preset, -P` | none | Optimization preset (see [Presets](#7-presets)) |

**Calibration & units:**

| Option | Default | Description |
|--------|---------|-------------|
| `--scale, -s` | none | Pixel-to-real-world scale. Format: `Npx=Nmm` (e.g. `64px=20mm`) |
| `--units` | `mm` | DXF header units: `mm`, `cm`, `in` |

**Quality options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--tolerance-mm` | `0.15` | Node reduction tolerance in mm |
| `--min-area, -a` | `100` | Minimum contour area in pixels |
| `--smoothing` | engine default | Smoothing tolerance |
| `--corner` | engine default | Corner sensitivity (0-180) |
| `--noise-filter` | engine default | Noise filtering level (1-10) |

**Output options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir, -o` | `./output` | Output directory |
| `--dxf-version` | `R2010` | DXF version: `R12`, `R2010`, `R2018` |
| `--qa / --no-qa` | enabled | Display QA report |

**Preprocessing:**

| Option | Description |
|--------|-------------|
| `--deskew-perspective` | Auto perspective correction before conversion |

**LLM pipeline options:**

| Option | Description |
|--------|-------------|
| `--provider` | Vision LLM provider (google, openai, anthropic, ollama, ...) |
| `--provider-model` | Full LiteLLM model string (e.g. `openai/gpt-4o`) |
| `--crew / --no-crew` | Use multi-agent CrewAI pipeline |

**Examples:**

```bash
# Basic conversion
dxfvec convert photo.png

# High-precision laser cutting
dxfvec convert drawing.png --engine advanced --tolerance-mm 0.05 --dxf-version R2018

# With calibration
dxfvec convert blueprint.png --scale 96px=1in --units in --dxf-version R2010

# Use a preset
dxfvec convert logo.png --preset logo_engrave --engine advanced

# LLM vision pipeline
dxfvec convert sketch.png --provider google --crew

# Centerline tracing for thin lines
dxfvec convert wiring.png --trace-mode centerline
```

### `dxfvec batch`

Batch convert all images in a directory.

```
dxfvec batch INPUT_DIR [OPTIONS]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir, -o` | `./batch_output` | Output directory |
| `--format, -f` | `zip` | Output format: `zip` or `dir` |
| `--engine, -e` | `classic` | Vectorization engine |
| `--recursive, -r` | off | Scan subdirectories |
| `--max-files` | 0 (unlimited) | Max files to process |
| `--mode, -m` | `lines` | DXF mode |
| `--preset, -P` | none | Optimization preset |
| `--scale, -s` | none | Pixel-to-real-world scale |
| `--tolerance-mm` | none | Node reduction tolerance |
| `--dxf-version` | `R2010` | DXF version |
| `--units` | `mm` | DXF header units |
| `--trace-mode` | `outline` | Trace mode |
| `--detect-arcs / --no-detect-arcs` | enabled | Arc detection |

**Examples:**

```bash
# Batch convert a folder
dxfvec batch ./drawings/

# Recursive with zip output
dxfvec batch ./drawings/ --recursive --format zip

# Limit to 10 files with advanced engine
dxfvec batch ./drawings/ --max-files 10 --engine advanced

# With preset and calibration
dxfvec batch ./logos/ --preset logo_engrave --scale 64px=20mm
```

**Output:**
- Each image gets its own subfolder with DXF, SVG, and PNG preview
- `summary.csv` and `summary.json` with per-file stats
- When `--format zip`: all results bundled into `batch_output.zip`

> **Note:** Cloud engines (`cloud:*`) fall back to Classic in batch mode. Use `dxfvec convert --engine cloud:...` for individual cloud conversions.

### `dxfvec modify`

Pre-process an image before vectorization.

```
dxfvec modify IMAGE [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--rotate, -r` | Rotate by degrees (e.g. `--rotate 90`) |
| `--resize, -rs` | Scale factor (e.g. `--resize 2` for 2x) |
| `--resize-width, -w` | Target width in pixels |
| `--resize-height, -h` | Target height in pixels |
| `--enhance / --no-enhance` | Enhance contrast |
| `--denoise / --no-denoise` | Remove noise |
| `--sharpen / --no-sharpen` | Sharpen edges |
| `--deskew / --no-deskew` | Auto-correct rotation |
| `--output, -o` | Output file path |

**Example:**

```bash
dxfvec modify scan.png --rotate 1.5 --deskew --enhance --denoise --sharpen
```

### `dxfvec enhance`

One-click enhancement for scanned drawings.

```
dxfvec enhance IMAGE [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--output-dir, -o` | Output directory (default: `./output`) |

Produces two files: `enhanced.png` (denoised) and `binary.png` (binarized).

```bash
dxfvec enhance scanned_drawing.png --output-dir ./preprocessed/
```

### Informational commands

```bash
# List available engines and dependency versions
dxfvec engines

# List optimization presets with parameter details
dxfvec presets

# List cloud AI providers and configuration status
dxfvec providers

# Show Python and all dependency versions
dxfvec info
```

---

## 7. Engines

### Classic Engine

**Default engine.** Uses OpenCV contour tracing for fast, deterministic vectorization.

```bash
dxfvec convert image.png --engine classic
```

| Property | Value |
|----------|-------|
| API keys required | No |
| Speed | Fast |
| Quality | Good for clean line drawings |
| Best for | CNC cutting, laser engraving, technical drawings |

**How it works:**
1. Adaptive threshold or Canny edge detection
2. Contour tracing via `cv2.findContours`
3. PathModel assembly from contour points
4. Optional arc/circle detection (Taubin least-squares fitting)
5. Douglas-Peucker node reduction
6. DXF export with CNC layer assignment

### Advanced Engine

Uses VTracer for AI-style vectorization with smooth, high-quality paths.

```bash
dxfvec convert image.png --engine advanced
```

| Property | Value |
|----------|-------|
| API keys required | No |
| Speed | Moderate |
| Quality | High — smooth Bezier-like paths |
| Best for | Logos, artwork, complex shapes with curves |

**How it works:**
1. VTracer converts image to SVG with Bezier curves
2. SVG path data is parsed (M, L, C, Q, A, Z commands)
3. Bezier curves subdivided into line segments
4. PathModel assembled with arc detection
5. DXF export with CNC layer assignment

### Cloud AI Engines (BYOK)

External APIs for highest quality on complex images. Requires API keys.

```bash
dxfvec convert image.png --engine cloud:vectorizer_ai
```

| Provider | Env vars | Notes |
|----------|----------|-------|
| Vectorizer.AI | `DXVEC_VECTORIZER_AI_API_ID`, `DXVEC_VECTORIZER_AI_API_SECRET` | Commercial API |
| DXFai | `DXVEC_DXFAI_API_KEY` | Placeholder — API not publicly documented |

```bash
# Check provider status
dxfvec providers
```

---

## 8. Presets

Presets are pre-configured parameter sets optimized for specific use cases.

| Preset | Description | Use case |
|--------|-------------|----------|
| `logo_engrave` | High-detail, tight tolerance | Logos, artwork, intricate designs |
| `laser_stencil` | Simplified paths, fast cutting | Laser cutting stencils, rapid prototyping |
| `technical_drawing` | Preserves dimensions and precision | Engineering drawings, blueprints |
| `contour_map` | Fine detail, minimal filtering | Topographic maps, contour lines |

**Usage:**

```bash
dxfvec convert image.png --preset logo_engrave
dxfvec batch ./drawings/ --preset laser_stencil
```

**Preset parameters:**

| Parameter | logo_engrave | laser_stencil | technical_drawing | contour_map |
|-----------|-------------|---------------|-------------------|-------------|
| min_area | 50 | 200 | 100 | 30 |
| tolerance_mm | 0.08 | 0.25 | 0.10 | 0.05 |
| noise_filter | 2 | 5 | 3 | 1 |
| corner_threshold | 70 | 40 | 60 | 80 |

You can override any preset parameter via CLI flags:

```bash
# Use preset but override tolerance
dxfvec convert image.png --preset logo_engrave --tolerance-mm 0.02
```

---

## 9. Calibration & Units

Calibration maps pixel dimensions to real-world measurements, enabling dimensionally accurate DXF output.

### Setting calibration via CLI

```bash
# Format: Npx=Nmm (N pixels = N millimeters)
dxfvec convert image.png --scale 64px=20mm

# Other units
dxfvec convert image.png --scale 96px=1in
dxfvec convert image.png --scale 38px=1cm

# Direct ratio (pixels per mm)
dxfvec convert image.png --scale 3.2
```

### Setting calibration via Web UI

1. Open the web UI at `http://localhost:5000`
2. Upload an image
3. Enter "Reference pixel length" (e.g., 64)
4. Enter "Real-world length" (e.g., 20)
5. Select unit (mm, cm, in)

### How calibration works

- DXFvec computes `scale_factor = real_world_length / reference_px_length`
- All coordinates in the DXF are scaled to real-world units
- The DXF header `$INSUNITS` is set to match (0=unitless, 1=inches, 4=mm, 5=cm)
- QA report shows dimensional accuracy percentage

### Calibration tips

- **Measure a known feature**: Use a ruler to measure a line or circle in the original drawing
- **Be precise**: Enter the pixel count carefully (zoom in to count pixels)
- **Reasonable values**: Scale factor must be > 0 and < 1,000,000
- **Unit consistency**: The DXF header units match your chosen unit

---

## 10. DXF Output Details

### Layer Semantics

DXFvec automatically assigns entities to CNC-ready layers:

| Layer | Color | ACI | Purpose | Typical use |
|-------|-------|-----|---------|-------------|
| CUT | Red | 1 | Cut paths | Laser/waterjet cutting, CNC routing |
| ENGRAVE | Blue | 5 | Engrave fills | Laser engraving, marking |
| BEND | Blue (dashed) | 5 | Bend lines | Sheet metal bending |
| DIM | Green | 3 | Dimensions | Reference dimensions |
| SCRAP | Gray | 8 | Discarded geometry | Not exported to final DXF |

### DXF Versions

| Version | Compatibility | Features |
|---------|--------------|----------|
| `R12` | All CAD/CAM software | Basic entities, maximum compatibility |
| `R2010` | AutoCAD 2010+ (default) | LWPOLYLINE, ARC, CIRCLE, proper headers |
| `R2018` | AutoCAD 2018+ | Latest DXF features |

**Recommendation:** Use `R2010` for most workflows. Use `R12` for legacy CAM software. Use `R2018` for modern AutoCAD-only workflows.

### Arc & Circle Detection

When `--detect-arcs` is enabled (default), DXFvec detects circular arcs and full circles and exports them as native DXF `ARC` and `CIRCLE` entities instead of polyline approximations.

**How it works:**
1. Points are analyzed for circular arc patterns
2. Taubin least-squares fitting estimates circle center and radius
3. Arc segments are identified (start/end angles)
4. Full circles (360° arcs) are exported as `CIRCLE` entities
5. Partial arcs are exported as `ARC` entities with correct start/end angles

**Benefits:**
- Native ARC/CIRCLE entities are smaller file size
- CAD software can dimension arcs directly
- CAM software can optimize toolpaths for arcs
- True geometry instead of faceted approximations

---

## 11. QA Reports

Every conversion produces a QA report (displayed in CLI, downloadable in web UI).

**Report contents:**

| Field | Description |
|-------|-------------|
| Entity count | Total DXF entities |
| Closed path count | Paths suitable for cutting |
| Open path count | Paths that may be incomplete |
| Segment count | Total line/arc/bezier segments |
| Node count | Total vertices |
| Layers | List of layers with entity counts |
| Calibrated | Whether real-world units are set |
| DXF audit | Pass/fail from ezdxf validation |
| Bounding box | Min/max coordinates with units |
| Dimensional accuracy | Estimated accuracy percentage |

**CLI output example:**

```
--------------------------------------------------
 QA Report
--------------------------------------------------
  Entities:     47
  Closed paths: 12
  Open paths:   0
  Segments:     203
  Nodes:        156
  Layers:       2
  Calibrated:   yes
  DXF audit:    PASS

  Layer 'CUT': 12 entities (ACI 1)
  Layer 'ENGRAVE': 35 entities (ACI 5)

  Bounding box: 0.0, 0.0 -> 127.0, 89.0 [mm]
  Dimensional accuracy: 99.87%
--------------------------------------------------
```

**Critical issues to watch for:**
- **Open paths**: May indicate incomplete geometry. For CNC cutting, all CUT paths should be closed.
- **DXF audit FAIL**: Output may be corrupt. Try a different engine or reduce image complexity.
- **Low dimensional accuracy**: Check your calibration settings.

---

## 12. Web UI

### Starting the server

```bash
# Development
python -m dxfvec.web

# Production (Gunicorn)
gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 300 dxfvec.web:app
```

Open `http://localhost:5000` in your browser.

### Single Image Upload

1. **Drag & drop** or click to select an image
2. **Configure options:**
   - Engine selection (Classic / Advanced / Cloud)
   - DXF mode (Lines / Hatch / Faces)
   - Trace mode (Outline / Centerline)
   - Arc detection toggle
   - DXF version (R12 / R2010 / R2018)
   - Units (mm / cm / in)
   - Preset selection
3. **Set calibration** (optional):
   - Reference pixel length
   - Real-world length
   - Unit
4. **Click Convert**
5. **Download** the resulting ZIP (DXF + SVG + PNG preview)

### Batch Upload

1. **Create a ZIP** containing images (PNG, JPG, WEBP, BMP, TIFF)
2. **Drag & drop** the ZIP onto the batch upload area
3. **Configure options** (same as single upload)
4. **Click Convert**
5. Download the batch ZIP with all results + summary CSV/JSON

**Limits:**
- Max 20 images per batch
- Max 20 MB per image
- Supported formats: PNG, JPG, JPEG, WEBP, BMP, TIFF

### DXF Viewer

After conversion, click **"View DXF"** to open the interactive canvas viewer:

- **Pan**: Click and drag
- **Zoom**: Mouse wheel
- **Toggle views**: Raster / Vector / Overlay
- **Show nodes**: Toggle vertex display
- **Print / PDF**: Direct print or PDF export
- **Download**: DXF and SVG downloads

### File Gallery

Browse all previous conversions at `/files`:

- View file names, sizes, and dates
- Download DXF, SVG, or full ZIP bundle
- View DXF in the canvas viewer
- Delete old files

---

## 13. REST API

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Upload form (single + batch) |
| `/convert` | POST | Convert image (multipart form) |
| `/api/batch` | POST | Batch convert ZIP of images |
| `/download/<filename>` | GET | Download ZIP bundle (DXF + SVG + PNG) |
| `/view/<filename>` | GET | DXF canvas viewer |
| `/files` | GET | File gallery page |
| `/api/engines` | GET | List engines and presets |
| `/api/presets` | GET | List presets with parameters |
| `/api/providers` | GET | List cloud providers and status |
| `/api/dxf/<name>` | GET | DXF entities as JSON (for viewer) |
| `/api/pdf` | POST | Generate PDF from image |
| `/api/ping` | GET | Health check |

### Convert endpoint

```bash
curl -X POST http://localhost:5000/convert \
  -F "image=@drawing.png" \
  -F "engine=classic" \
  -F "mode=lines" \
  -F "dxf_version=R2010" \
  -F "units=mm"
```

### Health check

```bash
curl http://localhost:5000/api/ping
# {"status": "ok", "version": "2.0.0"}
```

---

## 14. LLM Vision Pipeline

The LLM vision pipeline uses large language models with vision capabilities to analyze images and generate geometry JSON, which is then converted to DXF.

### Setup

1. Install the crew extra:
   ```bash
   pip install -e ".[crew]"
   ```

2. Configure API keys in `.env`:
   ```bash
   cp .env.example .env
   # Edit .env and set at least one provider key
   ```

3. Supported providers (12 total):

   | Provider | Env var | Default model |
   |----------|---------|---------------|
   | Google Gemini | `GEMINI_API_KEY` | gemini-2.0-flash |
   | OpenAI | `OPENAI_API_KEY` | gpt-4o |
   | Anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 |
   | Groq | `GROQ_API_KEY` | llama-3.2-90b-vision-preview |
   | Mistral | `MISTRAL_API_KEY` | mistral-large-latest |
   | Ollama | (local server) | llama3.2-vision |
   | OpenRouter | `OPENROUTER_API_KEY` | google/gemini-2.0-flash |
   | Cerebras | `CEREBRAS_API_KEY` | llama-3.2-vision |
   | Cohere | `COHERE_API_KEY` | command-r-vision |
   | NVIDIA | `NVIDIA_API_KEY` | nvidia/llama-3.1-nemotron-ultra-253b-v1 |
   | xAI | `XAI_API_KEY` | grok-2-vision |

### Single LLM Call

```bash
dxfvec convert sketch.png --provider google
dxfvec convert sketch.png --provider openai --provider-model "openai/gpt-4o"
```

The pipeline:
1. Preprocesses the image (grayscale, denoise, binarize)
2. Sends the image to the LLM with a geometry extraction prompt
3. Parses the LLM's JSON response
4. Scales geometry if calibration is provided
5. Exports to DXF

### CrewAI Multi-Agent

Uses a three-agent pipeline for higher quality:

```bash
dxfvec convert sketch.png --provider google --crew
```

**Agents:**
1. **Vision Analyst**: Analyzes the image and extracts geometry
2. **DXF Builder**: Converts geometry to DXF-ready format
3. **QA Reviewer**: Reviews and validates the output

---

## 15. Python API

### Basic conversion

```python
from pathlib import Path
from dxfvec import ClassicEngine, AdvancedEngine

# Classic engine
engine = ClassicEngine()
result = engine.convert(
    image_path=Path("drawing.png"),
    output_dir=Path("./output"),
    config={
        "dxf_mode": "lines",
        "dxf_version": "R2010",
        "trace_mode": "outline",
        "detect_arcs": True,
        "cnc_layers": True,
        "units": "mm",
    },
)
print(result["dxf"])        # Path to DXF file
print(result["svg"])        # Path to SVG file
print(result["qa_report"])  # QA report dict
```

### Using presets

```python
from dxfvec import AdvancedEngine, apply_preset

config = {"dxf_mode": "lines", "dxf_version": "R2010"}
config = apply_preset(config, "logo_engrave")

engine = AdvancedEngine()
result = engine.convert(image_path, output_dir, config)
```

### PathModel (canonical geometry)

```python
from dxfvec import PathModel, Path, polyline_to_path, circle_to_path

model = PathModel()

# Add a polyline (closed CUT path)
path = polyline_to_path(
    points=[(0, 0), (10, 0), (10, 10), (0, 10)],
    layer="CUT",
    closed=True,
)
model.paths.append(path)

# Add a circle
circle = circle_to_path(
    cx=5.0, cy=5.0, radius=2.5,
    layer="ENGRAVE",
    n_points=32,
)
model.paths.append(circle)

# Export
from dxfvec import write_dxf, write_svg
write_dxf(model, Path("output.dxf"), dxf_version="R2010", units="mm")
write_svg(model, Path("output.svg"))
```

### QA reports

```python
from dxfvec import generate_qa_report, save_qa_report

qa = generate_qa_report(model, output_dir=Path("./qa"))
save_qa_report(qa, Path("./qa/report.json"), Path("./qa/report.md"))
```

### Image preprocessing

```python
from dxfvec import preprocess
import cv2

img = cv2.imread("scan.png")
processed = preprocess(img, output_dir=Path("./preprocessed"))
```

---

## 16. Docker Deployment

### Development

```bash
docker compose up -d
# Web UI at http://localhost:5000
```

### Production

```bash
docker build -t dxfvec .
docker run -d \
  -p 5000:5000 \
  -e GEMINI_API_KEY=your-key \
  -v dxfvec-data:/app/output \
  --name dxfvec \
  dxfvec
```

### Docker Compose

```yaml
services:
  dxfvec:
    build: .
    ports:
      - "5000:5000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - MAX_IMAGE_DIM=2048
    volumes:
      - dxfvec-data:/app/output

  dxfvec-worker:
    build: .
    command: python -m dxfvec.cli batch /app/batch_input --format dir --output-dir /app/batch_output
    volumes:
      - dxfvec-data:/app/output
```

### Docker features

- Non-root `dxfvec` user
- Read-only filesystem with tmpfs at `/tmp`
- Gunicorn with 1 worker (OpenCV memory constraints)
- `PYTHONUNBUFFERED=1` for streaming logs
- `PYTHONDONTWRITEBYTECODE=1` for smaller image

---

## 17. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `5000` | Web server port |
| `FLASK_DEBUG` | `0` | Enable Flask debug mode |
| `MAX_IMAGE_DIM` | `2048` | Max image dimension in pixels |
| `DOWNLOAD_TTL` | `3600` | Temp file TTL in seconds |
| `PYTHONUNBUFFERED` | `1` | Stream logs (Docker) |
| `PYTHONDONTWRITEBYTECODE` | `1` | Skip .pyc files (Docker) |

### LLM Provider keys

| Variable | Provider |
|----------|----------|
| `GEMINI_API_KEY` | Google Gemini |
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `GROQ_API_KEY` | Groq |
| `MISTRAL_API_KEY` | Mistral |
| `CEREBRAS_API_KEY` | Cerebras |
| `COHERE_API_KEY` | Cohere |
| `NVIDIA_API_KEY` | NVIDIA NIM |
| `XAI_API_KEY` | xAI / Grok |
| `OPENROUTER_API_KEY` | OpenRouter |
| `OLLAMA_API_KEY` | Ollama (local) |

### Cloud engine keys

| Variable | Provider |
|----------|----------|
| `DXVEC_VECTORIZER_AI_API_ID` | Vectorizer.AI |
| `DXVEC_VECTORIZER_AI_API_SECRET` | Vectorizer.AI |
| `DXVEC_DXFAI_API_KEY` | DXFai |

---

## 18. Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ImportError: libGL.so.1` | Missing OpenCV system libs | `sudo apt install libglib2.0-0 libgomp1` |
| `ModuleNotFoundError: litellm` | LLM extras not installed | `pip install -e ".[crew]"` |
| `ModuleNotFoundError: flask` | Web extras not installed | `pip install -e ".[web]"` |
| DXF output has no ARC entities | Arc detection disabled or pixel-space only | Use `--detect-arcs` and `--scale` |
| DXF audit fails | Corrupt output | Try different engine, reduce image complexity |
| Web UI upload fails silently | File too large or wrong format | Check file size (<20MB) and format (PNG/JPG/WEBP/BMP/TIFF) |
| Batch drops cloud engines | Known limitation | Use `dxfvec convert --engine cloud:...` per image |
| `.env` changes not picked up | LiteLLM cached old values | Restart the process |
| OpenCV import is slow | Antivirus scanning | Add `.venv` to AV exclusions |
| PowerShell activation fails | Execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| DXF coordinates are huge | Missing calibration | Add `--scale Npx=Nmm` |
| DXF coordinates are tiny | Scale factor inverted | Check `Npx=Nmm` format (pixels on left, mm on right) |

---

## 19. FAQ

**Q: Do I need a GPU?**
No. DXFvec is entirely CPU-based. OpenCV, VTracer, and all processing run on the CPU.

**Q: Do I need API keys?**
Not for the Classic or Advanced engines. API keys are only needed for Cloud AI engines (`cloud:*`) or the LLM vision pipeline (`--provider`).

**Q: Which engine should I use?**
- **Classic**: Fast, deterministic. Best for clean line drawings and CNC workflows.
- **Advanced (VTracer)**: Higher quality paths. Best for logos, artwork, and curved shapes.
- **Cloud AI**: Highest quality for complex images. Requires API keys.

**Q: What DXF version should I use?**
- **R12**: Maximum compatibility with legacy CAM software.
- **R2010**: Recommended default. Works with all modern CAD/CAM.
- **R2018**: Only if you need the latest DXF features and use AutoCAD 2018+.

**Q: How do I get dimensionally accurate DXF output?**
Use the `--scale` option with a known measurement: `--scale 64px=20mm`. Measure a feature in the original image (pixel count) and its real-world size.

**Q: Can I run the web UI in production?**
Yes, but use Gunicorn: `gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 300 dxfvec.web:app`. Use `--workers 1` due to OpenCV memory constraints.

**Q: How do I customize a preset?**
Apply the preset and override individual parameters:
```bash
dxfvec convert image.png --preset logo_engrave --tolerance-mm 0.02 --min-area 30
```

**Q: Can I use DXFvec as a library in my Python project?**
Yes. See [Python API](#14-python-api) for examples. Core classes: `ClassicEngine`, `AdvancedEngine`, `PathModel`, `write_dxf`.

**Q: What image formats are supported?**
PNG, JPG, JPEG, WEBP, BMP, TIFF (including multi-page TIFF).

**Q: How do I contribute?**
See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, code conventions, and PR guidelines.
