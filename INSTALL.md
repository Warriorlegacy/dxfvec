# DXFvec Installation Guide

## Prerequisites

- **Python 3.10+** (3.10 or 3.11 recommended; 3.12+ untested)
- **pip** 21.0+ (included with Python 3.10+)
- **Virtual environment** (recommended for all install methods)

**OS-specific notes:**
- **Linux** — requires OpenCV system libraries: `libglib2.0-0` and `libgomp1` (see [Linux-Specific Notes](#linux-specific-notes)).
- **macOS** — no extra system libraries needed. Use the system Python or a Homebrew/managed install.
- **Windows** — `opencv-python-headless` wheels are used; no extra system libraries needed.

---

## Quick Install

Choose the method that matches your use case:

```bash
# CLI-only (recommended for end users)
pipx install dxfvec

# Development with venv
python -m venv .venv && .venv\Scripts\activate   # Windows
source .venv/bin/activate                        # macOS / Linux
pip install -e ".[web,crew]"

# Editable with all extras
git clone https://github.com/yourorg/dxfvec.git && cd dxfvec
python -m venv .venv && source .venv/bin/activate
pip install -e ".[web,crew,dev]"
```

---

## All Install Methods

### pipx (recommended for CLI-only usage)

```bash
pipx install dxfvec
dxfvec engines
```

Installs a global, isolated CLI. No virtualenv activation required.

### venv + pip (recommended for development)

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate   # macOS / Linux
pip install dxfvec
```

### Editable install with extras

```bash
pip install -e ".[web,crew]"
```

Useful if you want to modify the source or install LLM vision pipeline support.

### Wheel / sdist

```bash
pip install dxfvec==2.0.0
```

Pulls the published wheel from PyPI.

### From source

```bash
git clone https://github.com/yourorg/dxfvec.git && cd dxfvec
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .
```

---

## Optional Extras

| Extra | Installs | Use case |
|-------|---------|---------|
| `web` | flask, gunicorn, flask-cors | Run the web UI (`dxfvec.web`) |
| `crew` | crewai, litellm | LLM vision pipeline (`--provider`) |
| `dev` | ruff, mypy, pytest, pytest-timeout | Lint, typecheck, and run tests |
| `cloud` | requests (usually already present) | BYOK cloud engine wrappers |

Install multiple extras:

```bash
pip install -e ".[web,crew,dev]"
```

---

## Windows-Specific Notes

Activate the virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

`opencv-python-headless` wheels are used by default; no Visual C++ redistributable is needed beyond what Python ships with.

---

## macOS-Specific Notes

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[web,crew]"
```

No additional system libraries are required. If you use a non-system Python (e.g., Homebrew), ensure it is on your `PATH` before activating the venv.

---

## Linux-Specific Notes

Install required system libraries **before** creating the virtual environment:

```bash
sudo apt update
sudo apt install -y libglib2.0-0 libgomp1
```

Then:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[web,crew]"
```

Without these packages, OpenCV will fail at import with `libGL.so.1` or `libgomp.so.1` errors.

---

## Verify Installation

```bash
# List available vectorization engines
dxfvec engines

# Show LLM provider config
dxfvec providers

# Show built-in presets
dxfvec presets

# Quick smoke test
dxfvec info
```

If these commands run without error, the install is healthy.

---

## Uninstall

```bash
# pip-based installs
pip uninstall dxfvec

# pipx-based installs
pipx uninstall dxfvec
```

Remove the virtual environment directory (`.venv/`) if you created one.

---

## Environment Variables

Copy `.env.example` to `.env` and set the keys required by your workflow:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
# Server
PORT=5000
FLASK_DEBUG=0
MAX_IMAGE_DIM=2048
DOWNLOAD_TTL=3600

# LLM providers (LiteLLM reads .env automatically)
GEMINI_API_KEY=your-key
OPENAI_API_KEY=your-key
# ... other <PROVIDER>_API_KEY entries
```

LiteLLM reads `.env` from the project root automatically. No extra configuration is needed.

---

## Docker

```bash
docker compose up -d
```

Services:

- **dxfvec** — Flask web UI + CLI runtime (port 5000).
- **dxfvec-worker** — long-running `dxfvec batch` worker for queue-based processing.

The image runs as a non-root `dxfvec` user with a read-only filesystem and tmpfs at `/tmp`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ImportError: libGL.so.1` / `libgomp.so.1` | Missing OpenCV system libs on Linux | `sudo apt install libglib2.0-0 libgomp1` |
| `ModuleNotFoundError: No module named 'litellm'` | LLM extras not installed | `pip install -e ".[crew]"` |
| `ModuleNotFoundError: No module named 'flask'` | Web extras not installed | `pip install -e ".[web]"` |
| Permission denied on `.venv\Scripts\activate` | PowerShell execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `pipx` command not found | pipx not on PATH | Reinstall pipx or add `~/.local/bin` to PATH |
| OpenCV import hangs or is very slow | Antivirus / filesystem watcher on venv | Add `.venv` to AV exclusions |
| `dxfvec batch --engine cloud:*` falls back to Classic | Batch silently drops cloud engines | Use `dxfvec convert --engine cloud:vectorizer_ai` directly |
| `SyntaxError` on import / CLI missing | Python < 3.10 | Upgrade to Python 3.10+ |
| DXF output missing ARC entities | DXF version too old for arcs | Use `--dxf-version R2010` or later |
| `.env` changes not picked up | LiteLLM cached old values | Restart the process or clear LiteLLM cache |

---

## FAQ

**Q: Should I use pipx or a virtualenv?**
Use `pipx` if you only need the `dxfvec` CLI. Use a virtualenv if you are developing, need extras like `[crew]`, or want to modify the source.

**Q: Do I need a GPU?**
No. DXFvec is CPU-only. OpenCV and VTracer run on the CPU. The LLM vision pipeline uses remote APIs.

**Q: Why does `dxfvec batch` ignore `cloud:*` engines?**
The batch command currently routes only `advanced` and falls back to `ClassicEngine` for everything else. Use `dxfvec convert --engine cloud:vectorizer_ai` for cloud engines.

**Q: Can I run the web UI without installing extras?**
Yes, if `flask` and `gunicorn` are already installed separately. Otherwise use `pip install -e ".[web]"`.

**Q: How do I use an LLM provider?**
Set the provider's API key in `.env`, then run `dxfvec convert input.png --provider google`. The `.[crew]` extra must be installed.
