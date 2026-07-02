# AGENTS.md — DXFvec

## Project

Python package for raster image → DXF vector conversion. Three engines (Classic/OpenCV, Advanced/VTracer, Cloud AI/BYOK), web UI (Flask), and CLI (Click).

**Source layout:** `src/dxfvec/` — all package code lives here. `pyproject.toml` sets `where = ["src"]`.

## Commands

```bash
# Install (editable)
pip install -r requirements.txt && pip install -e .

# Tests
python -m pytest tests/ -v --timeout=60

# Lint (CI uses this)
ruff check src/ tests/

# Type check (CI runs but continues on error)
mypy src/ --ignore-missing-imports

# Smoke test (standalone, no pytest)
python test_smoke.py

# CLI
dxfvec convert input.png --engine classic --mode lines -o output/
dxfvec batch ./images/ --format zip
dxfvec engines / presets / providers

# Web server (dev)
python -m dxfvec.web  # http://localhost:5000

# Production
gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 300 dxfvec.web:app
```

## Architecture

- **`path_model.py`** — Canonical geometry (PathModel). Single source of truth for all engines and exporters.
- **`engines.py`** — ClassicEngine (OpenCV), AdvancedEngine (VTracer). Both produce PathModel → DXF.
- **`dxf_writer.py`** — Exports PathModel to DXF (native ARC/CIRCLE entities, not polylines). Runs `ezdxf.audit()` after every write.
- **`vectorizer.py`** — Core vectorization: Vectorizer, ImageModifier, ShapeDetector, DXFGenerator.
- **`qa_report.py`** — QA validation: open-path detection, self-intersection, bounding box, DXF audit.
- **`curve_fitting.py`** — Arc/circle detection + Douglas-Peucker simplification.
- **`web.py`** — Flask app with inline HTML template (no separate template files). Rate limiting, MIME sniffing, decompression bomb protection.
- **`cli.py`** — Click CLI: `convert`, `batch`, `modify`, `enhance`, `engines`, `presets`, `providers`.

## Key Conventions

- **Python 3.10+** required (uses `str | None`, `X | Y` union syntax).
- **DXF layers**: CUT (red/ACI 1), ENGRAVE (blue/ACI 5), BEND (blue dashed/ACI 5), DIM (green/ACI 7).
- **DXF versions**: R12 (legacy), R2010 (default), R2018. Set via `$INSUNITS` header.
- **Presets**: `logo_engrave`, `laser_stencil`, `technical_drawing`, `contour_map` — override min_area, tolerance, smoothing.
- **Calibration**: pixel-to-real-world scale (`Npx=Nmm` format). Stored in PathModel, declared in DXF header.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | 5000 | Server port |
| `FLASK_DEBUG` | 0 | Dev mode |
| `MAX_IMAGE_DIM` | 2048 | Max image dimension (px) |
| `DOWNLOAD_TTL` | 3600 | Temp file TTL (seconds) |
| `DXVEC_VECTORIZER_AI_API_ID/SECRET` | — | BYOK cloud provider |
| `DXVEC_DXFAI_API_KEY` | — | BYOK cloud provider |

## CI (`.github/workflows/ci.yml`)

Runs on push/PR to `main`. Matrix: Python 3.10 + 3.11. Steps: `ruff check` → `mypy` (soft fail) → `pytest tests/ -v --timeout=60`. Docker build only on `main` push.

## Gotchas

- Web UI HTML is a single large string in `web.py` (`HTML_TEMPLATE`), not separate files.
- Gunicorn runs with `--workers 1` due to OpenCV memory constraints.
- Docker image uses non-root user `dxfvec`. Read-only filesystem with tmpfs for `/tmp`.
- `requirements.txt` uses `opencv-python-headless` (not `opencv-python`) for server/Docker. `pyproject.toml` lists `opencv-python` for dev/CLI.
- The `dxfvec-worker` service in `docker-compose.yml` runs `python -m dxfvec.cli batch`.
