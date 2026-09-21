# Contributing to DXFvec

Thanks for your interest in contributing. This doc covers setup, tooling, and testing.

---

## Dev Setup

```bash
git clone https://github.com/yourorg/dxfvec.git
cd dxfvec
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev,web,crew]"
```

## Tooling

- **Lint**: `ruff check src/ tests/`
- **Type check**: `mypy src/ --ignore-missing-imports`
- **Tests**: `pytest tests/ -v --timeout=60`
- **CI matrix**: Python 3.10 + 3.11 on ubuntu-latest.

## Code Style

- Python 3.10+ syntax features; `from __future__ import annotations` in every source file.
- `ruff` formatting/import sorting enforced in CI.
- DXF layers: CUT (ACI 1), ENGRAVE (ACI 5), BEND (ACI 5 dashed), DIM (ACI 7), SCRAP (ACI 8).
- DXF versions: R12 / R2010 (default) / R2018.

## Commands

```bash
dxfvec convert input.png --engine classic --mode lines -o output/
dxfvec convert input.png --engine advanced --detect-arcs
dxfvec convert input.png --engine cloud:vectorizer_ai
dxfvec batch ./images/ --format zip
dxfvec modify input.png --rotate 90 --enhance --deskew
dxfvec enhance input.png
dxfvec engines
dxfvec presets
dxfvec providers
python -m dxfvec.web
```

## Reporting Issues

- Include Python version, OS, install method, and exact command run.
- Attach a small sample image if file-related.
- Include `dxfvec info` output for environment issues.
