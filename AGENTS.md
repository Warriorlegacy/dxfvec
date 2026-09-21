# AGENTS.md — DXFvec

## Project

Python package for raster image → DXF vector conversion. Three vectorization engines (Classic/OpenCV, Advanced/VTracer, Cloud AI/BYOK), LLM vision pipeline (LiteLLM, 12 providers with auto-fallback), CrewAI multi-agent pipeline, web UI (Flask), and CLI (Click).

**Source layout:** `src/dxfvec/` — all package code lives here. `pyproject.toml` sets `where = ["src"]`.

## Commands

```bash
# Install
pip install -r requirements.txt && pip install -e .

# Optional extras
pip install -e ".[web]"     # flask, gunicorn, flask-cors (included in requirements.txt)
pip install -e ".[crew]"    # crewai + litellm (AI pipelines)
pip install -e ".[cloud]"   # requests (already in base deps)

# Lint
ruff check src/ tests/

# Type check (soft-fail in CI)
mypy src/ --ignore-missing-imports

# Tests
python -m pytest tests/ -v --timeout=60

# Smoke test (standalone, no pytest)
python test_smoke.py

# CLI — engines-based conversion
dxfvec convert input.png --engine classic --mode lines -o output/
dxfvec convert input.png --engine advanced --detect-arcs --tolerance-mm 0.1
dxfvec convert input.png --engine cloud:vectorizer_ai
dxfvec batch ./images/ --format zip
dxfvec modify input.png --rotate 90 --enhance --deskew
dxfvec engines / presets / providers

# CLI — LLM vision pipeline (requires `pip install -e ".[crew]"`)
dxfvec convert input.png --provider google
dxfvec convert input.png --provider openai --provider-model "openai/gpt-4o"
dxfvec convert input.png --provider ollama  --crew     # local + CrewAI multi-agent

# Web server (dev)
python -m dxfvec.web  # http://localhost:5000

# Production
gunicorn --bind 0.0.0.0:5000 --workers 1 --timeout 300 dxfvec.web:app
```

## Architecture

- **`path_model.py`** — Canonical geometry (PathModel, Path, Segment types). Single source of truth for all engines, pipelines, and exporters.
- **`engines.py`** — ClassicEngine (OpenCV), AdvancedEngine (VTracer), Cloud AI. All produce PathModel → DXF via `write_dxf`. Includes presets, arc detection, DP simplification, QA reports.
- **`dxf_writer.py`** — Exports PathModel to DXF (native ARC/CIRCLE entities) and SVG. Runs `ezdxf.audit()` after every write. Supports R12/R2010/R2018. Exports `create_dxf()` as backward-compat wrapper around `write_dxf()`.
- **`vectorizer.py`** — Core OpenCV vectorization: adaptive threshold / Canny edge detection, contour tracing, PathModel assembly. 100% local, no API calls. Also exports legacy `vectorize_image()` and `DXFGenerator`.
- **`curve_fitting.py`** — Arc/circle detection (Taubin/Kasa least-squares) + Douglas-Peucker node reduction.
- **`qa_report.py`** — QA validation: open-path gap detection, self-intersection, bounding box, DXF audit.
- **`providers.py`** — LiteLLM vision abstraction. 12 providers with ordered fallback chain. Used by `pipeline.py` and `crew_pipeline.py`.
- **`pipeline.py`** — Single LLM vision call → geometry JSON → DXF. Accessible via `dxfvec convert --provider`.
- **`crew_pipeline.py`** — Three-agent CrewAI pipeline: Vision Analyst → DXF Builder → QA Reviewer. Accessible via `dxfvec convert --provider --crew`.
- **`preprocess.py`** — OpenCV image preprocessing: CLAHE, denoise, deskew, adaptive binarization. Used by LLM pipelines.
- **`ai_enhancer.py`** — Edge-aware enhancement (bilateral filter, mean shift, morphology). No AI API calls.
- **`cloud_providers.py`** — BYOK cloud API wrappers (Vectorizer.AI, DXFai). DXFai is a placeholder (API not publicly documented).
- **`web.py`** — Flask app with inline `HTML_TEMPLATE` string (no separate template files). Rate limiting, MIME sniffing, decompression bomb protection.
- **`cli.py`** — Click CLI: `convert`, `batch`, `modify`, `enhance`, `engines`, `presets`, `providers`.

## Key Conventions

- **Python 3.10+** (`str | None`, `X | Y` union). `from __future__ import annotations` in every source file.
- **DXF layers**: CUT (red/ACI 1), ENGRAVE (blue/ACI 5), BEND (blue dashed/ACI 5), DIM (ACI 7), SCRAP (gray/ACI 8).
- **DXF versions**: R12 (legacy), R2010 (default), R2018. `$INSUNITS` set from calibration.
- **Presets**: `logo_engrave`, `laser_stencil`, `technical_drawing`, `contour_map` — override min_area, tolerance, smoothing.
- **Enums**: DXFMode (LINES|HATCH|FACES), TraceMode (OUTLINE|CENTERLINE), LayerName, DXFVersion.
- **Calibration**: pixel-to-real-world scale (`Npx=Nmm` format). Stored in PathModel, declared in DXF header.
- **No ruff/mypy config files** — all tool config is implicit.
- **`__all__`** in `__init__.py`: update both exports and `__all__` when adding public APIs.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | 5000 | Server port |
| `FLASK_DEBUG` | 0 | Dev mode |
| `MAX_IMAGE_DIM` | 2048 | Max image dimension (px) |
| `DOWNLOAD_TTL` | 3600 | Temp file TTL (s) |
| `GEMINI_API_KEY` | — | Default LLM provider |
| `<PROVIDER>_API_KEY` | — | One per fallback provider |
| `DXVEC_VECTORIZER_AI_API_ID` | — | Vectorizer.AI API ID |
| `DXVEC_VECTORIZER_AI_API_SECRET` | — | Vectorizer.AI API secret |
| `DXVEC_DXFAI_API_KEY` | — | DXFai API key (placeholder) |
| `PYTHONUNBUFFERED` | 1 | Docker: stream logs |
| `PYTHONDONTWRITEBYTECODE` | 1 | Docker: no .pyc |
| `PYTHONPATH` | `/app/src` | Docker: import path |

`.env` contains live keys for fallback chain: google → openrouter → groq → mistral → openai → cerebras → cohere → nvidia → xai. LiteLLM reads `.env` automatically. **Commit history includes these keys — do not push new secrets.**

## CI (`.github/workflows/ci.yml`)

Push/PR to `main`. Matrix: Python 3.10 + 3.11. Steps: `ruff check` → `mypy` (soft fail) → `pytest -v --timeout=60`. Docker build only on `main` push.

## Gotchas

- **No `[dev]` extra** in `pyproject.toml` — CI runs `pip install -e ".[dev]"` which is a no-op. Install ruff, mypy, pytest manually for local dev.
- **LLM pipeline requires `.[crew]` extra.** The `--provider` flag on `dxfvec convert` only works with `pip install -e ".[crew]"`. Without it, `import litellm` will fail.
- **Three separate preprocessing pathways** that are not interchangeable: `vectorizer.py` has built-in auto-detection (drawing vs photo), `preprocess.py` is standalone for LLM pipelines, and `ai_enhancer.py` does bilateral + mean shift only.
- **`batch` command silently ignores cloud engines.** Line 349 falls back to `ClassicEngine()` for any engine that isn't `"advanced"` — `cloud:*` providers are silently dropped.
- **DIM layer color mismatch.** `path_model.py:LAYER_COLORS["DIM"] = 7` (white/gray), but `engines.py:_apply_cnc_layers` sets `DIM = 3` (green). Results depend on which code path runs.
- **Config dict pattern.** Engines share an untyped config dict (`build_config()` → `engine.convert()`). Adding a new parameter requires updating extraction at multiple sites.
- Web UI HTML is a single large string in `web.py:158` (`HTML_TEMPLATE`), not separate template files.
- Gunicorn runs with `--workers 1` due to OpenCV memory constraints.
- Docker image uses non-root user `dxfvec`. Read-only filesystem with tmpfs for `/tmp`.
- `requirements.txt` uses `opencv-python-headless` (server/Docker). `pyproject.toml` lists `opencv-python` for dev/CLI.
- `dxfvec-worker` in `docker-compose.yml` runs `python -m dxfvec.cli batch` in a loop.
- All test files add `sys.path.insert(0, ...)` for `src/` layout (redundant with editable install but harmless).
- Tests: 4 files — `test_curve_fitting.py`, `test_dxf_writer.py`, `test_path_model.py`, `test_qa_report.py`.
