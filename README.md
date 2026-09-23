# DXFvec

[![CI](https://github.com/Warriorlegacy/dxfvec/actions/workflows/ci.yml/badge.svg)](https://github.com/Warriorlegacy/dxfvec/actions/workflows/ci.yml)

**100% free image vectorization and DXF conversion** — no API keys required.
Convert raster images (PNG, JPG, WEBP, BMP, TIFF) into CAD/CNC-ready DXF vectors with CUT/ENGRAVE/BEND/DIM layer semantics.

## Features

### Core Vectorization
- **3 engines**: Classic (OpenCV, fast), Advanced (VTracer AI, high-quality), Cloud AI (BYOK)
- **3 DXF modes**: Lines (cut paths), Hatch (engrave fills), Faces (closed shapes)
- **4 presets**: Logo Engrave, Laser Stencil, Technical Drawing, Contour Map
- **Adaptive preprocessing**: Auto-detects drawing vs photo mode for optimal edge detection

### Industry-Grade DXF Output
- **Native ARC/CIRCLE entities**: True CAD geometry, not polyline approximations
- **DXF version selection**: R12 (legacy), R2010, R2018
- **CNC layers**: Auto-assigns CUT (red), ENGRAVE (blue), BEND (blue dashed), DIM (green)
- **Calibration**: Dimensional accuracy with real-world unit mapping (mm/cm/in)
- **Closed-loop enforcement**: Auto-closes CUT layer paths for CNC safety
- **DXF audit**: ezdxf validation after every write

### QA & Validation
- **QA reports**: Entity counts, layer distribution, open path detection, self-intersection check
- **Critical issue gating**: Warns on open paths or audit failures before download
- **Node reduction**: Tolerance-based Douglas-Peucker simplification (explicit mm, not abstract slider)

### Web UI
- **Drag-and-drop upload**: Single images and batch ZIP archives
- **Calibration tool**: Set real-world dimensions for accurate CAD output
- **Batch convert**: Process up to 20 images from a ZIP archive
- **Canvas viewer**: Pan/zoom, raster/vector/overlay toggle, node display
- **Print & PDF**: Direct printing and PDF export from viewer
- **File gallery**: Browse and download previous conversions

### CLI
```bash
dxfvec convert image.png [--engine classic|advanced|cloud:provider] [--mode lines|hatch|faces]
dxfvec modify image.png [--rotate 90] [--resize 800x600] [--enhance] [--denoise] [--sharpen] [--deskew]
dxfvec engines
dxfvec presets
dxfvec providers
```

### Security & Production
- **Non-root Docker**: Production-ready container with security hardening
- **Rate limiting**: 30 requests per minute per IP
- **Input validation**: MIME sniffing, decompression bomb protection, file size limits
- **Structured logging**: Full pipeline tracing for debugging
- **Health checks**: Built-in `/api/ping` endpoint

## Quick Start

```bash
# CLI users (recommended)
pipx install dxfvec
dxfvec engines

# Developers
git clone https://github.com/yourorg/dxfvec.git
cd dxfvec
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[web,crew]"
dxfvec engines
```

See [INSTALL.md](INSTALL.md) for platform-specific notes, Docker, and Azure/GCP/Render deployment.

## CLI

```bash
dxfvec convert image.png --engine classic --mode lines -o output/
dxfvec convert image.png --engine advanced --detect-arcs --tolerance-mm 0.1
dxfvec convert image.png --scale 64px=20mm --dxf-version R2018
dxfvec batch ./images/ --format zip --engine advanced
dxfvec modify image.png --rotate 90 --resize 2 --enhance --denoise --sharpen --deskew
dxfvec enhance image.png
dxfvec engines
dxfvec presets
dxfvec providers
dxfvec info
```

### Batch processing

```bash
dxfvec batch ./drawings/ --format zip --max-files 50 --recursive
```

> Note: cloud engines (`cloud:*`) fall back to Classic in batch mode. Use `dxfvec convert --engine cloud:...` for cloud jobs.

### LLM vision pipeline

Requires the `.[crew]` extra and API keys in `.env`:

```bash
cp .env.example .env
# set keys in .env

dxfvec convert image.png --provider google
dxfvec convert image.png --provider openai --provider-model "openai/gpt-4o" --crew
```

### Web server

```bash
python -m dxfvec.web
# Open http://localhost:5000
```

### Production (Docker)

```bash
docker compose up -d
# or
docker build -t dxfvec . && docker run -p 5000:5000 dxfvec
```

### Render Deployment

```bash
# Push to GitHub, then deploy on Render
# render.yaml auto-configures Docker deployment
# Result: https://dxfvec.onrender.com
```

## API Endpoints

| Route | Method | Description |
|---|---|---|
| `/` | GET | Upload form (single + batch) |
| `/convert` | POST | Convert image (multipart form) |
| `/api/batch` | POST | Batch convert ZIP of images |
| `/download/<filename>` | GET | Download ZIP bundle (DXF + SVG + PNG) |
| `/view/<filename>` | GET | DXF canvas viewer |
| `/files` | GET | File gallery |
| `/api/engines` | GET | List engines + presets |
| `/api/presets` | GET | List presets |
| `/api/providers` | GET | List cloud providers |
| `/api/dxf/<name>` | GET | DXF entities as JSON |
| `/api/ping` | GET | Health check |

## BYOK Cloud Providers

Set environment variables to enable cloud AI engines:

```bash
# Vectorizer.AI
DXVEC_VECTORIZER_AI_API_ID=your_id
DXVEC_VECTORIZER_AI_API_SECRET=your_secret

# DXFai
DXVEC_DXFAI_API_KEY=your_key
```

## Deployment

- **Render**: `render.yaml` configured — push to `main` triggers auto-deploy
- **Docker**: `docker compose up -d`
- **Docs**: See [DEPLOY.md](DEPLOY.md) for full deployment guide

## Tests

```bash
# Install the dev extra (ruff, mypy, pytest, pytest-timeout)
pip install -e ".[dev]"
# Full suite — 158 tests across 10 files
python -m pytest tests/ -v --timeout=60

# Standalone smoke test (no pytest)
python test_smoke.py

# Lint & type check (CI steps)
ruff check src/ tests/
mypy src/ --ignore-missing-imports
```

**158 tests** covering `curve_fitting`, `dxf_writer`, `engines`, `path_model`,
`path_model_extended`, `pipeline`, `preprocess`, `providers`, `qa_report`, and
`opencv_compat` (the OpenCV 5.x compatibility regression suite). CI runs the same
command on Python 3.10 and 3.11 via `.github/workflows/ci.yml`.

## Benchmarks

Reproducible performance numbers live in `benchmarks/`, produced by the harness in
`benchmarks/run_benchmarks.py`. See [BENCHMARKS.md](BENCHMARKS.md) for methodology and
measured results.

## Environment Variables

```bash
cp .env.example .env
```

Set keys for the LLM fallback chain or cloud engines. LiteLLM reads `.env` automatically. See [INSTALL.md](INSTALL.md) for the full env table.

## Deployment

- **Render**: `render.yaml` configured — push to `main` triggers auto-deploy
- **Docker**: `docker compose up -d`
- **Docs**: See [INSTALL.md](INSTALL.md) and [DEPLOY.md](DEPLOY.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, linting, and conventions.

## License

Apache-2.0 — see [LICENSE](LICENSE).
