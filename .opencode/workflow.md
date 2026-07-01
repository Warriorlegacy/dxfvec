# DXFvec — OpenCode Autonomous Build & Deploy Workflow

**Workflow name:** `dxfvec-continuous-deploy`  
**Project root:** `D:\DXFvec`  
**Trigger:** on push to `main`, on manual dispatch, on schedule  
**Environments:** local Docker, Render, Vercel, Railway, Fly.io  
**Artifacts:** build logs, test reports, deployment URLs, health-check results  
**On failure:** stop pipeline, report diagnostics, optionally trigger rollback

---

## 1. Pre-flight Checks

**Goal:** validate environment, config, and secrets before any build work.

### 1.1 Files & Config Validation
- Verify these files exist:
  - `pyproject.toml`
  - `requirements.txt`
  - `Dockerfile`
  - `docker-compose.yml`
  - `Procfile`
  - `render.yaml`
  - `vercel.json`
  - `src/dxfvec/web.py`
  - `src/dxfvec/engines.py`
  - `src/dxfvec/dxf_writer.py`
  - `src/dxfvec/cli.py`
  - `test_smoke.py`
- If any required file is missing: **fail fast** with a diff-like report listing absent paths.

### 1.2 Python Version Check
- Require Python >= 3.10.
- Read `pyproject.toml` `requires-python` and `render.yaml` `PYTHON_VERSION`.
- If host Python is older than 3.10: **fail** with guidance to upgrade.

### 1.3 Secrets / BYOK Sanity Check
- Read cloud provider env keys:
  - `DXVEC_VECTORIZER_AI_API_ID`
  - `DXVEC_VECTORIZER_AI_API_SECRET`
  - `DXVEC_DXFAI_API_KEY`
- If any are set but malformed (empty string, obviously truncated): **warn** but do not fail.
- Never print secret values; mask all keys in logs.

### 1.4 Git Hygiene
- Ensure working tree is clean or only contains expected deployment artifacts.
- Record current commit SHA for traceability.
- If uncommitted changes exist outside the allowed deployment artifact list: **warn**.

---

## 2. Install Dependencies

**Goal:** provision a clean, reproducible environment.

### 2.1 Virtual Environment
- Create `.venv` if missing.
- Use `python -m venv .venv` and activate it for all subsequent commands.

### 2.2 Core Install
- Run: `pip install --upgrade pip`
- Run: `pip install -r requirements.txt`
- Run: `pip install -e ".[web,cloud]"`

### 2.3 Failure Handling
- If any install step exits non-zero: **stop**, save pip logs to `logs/install-<timestamp>.log`, and emit a summary including:
  - missing system packages hint:
    - `libgl1-mesa-glx`
    - `libglib2.0-0`
    - `libsm6`
    - `libxext6`
    - `libxrender-dev`
  - Python/Pip version used.
- Suggest remediation based on error type:
  - `vtracer` wheel missing → use Python 3.10/3.11 on x86_64.
  - `opencv-python` import error → confirm system libs above.

---

## 3. Static Analysis & Smoke Tests

**Goal:** cheap, fast checks before any long-running or network operation.

### 3.1 Import Smoke Test
- Run: `python -c "import dxfvec; from dxfvec.engines import ClassicEngine, AdvancedEngine; from dxfvec.cloud_providers import list_cloud_providers; print('OK')"`
- If this fails: **stop** and attach traceback to `logs/import-error-<timestamp>.log`.

### 3.2 Package Smoke Test
- Run: `py test_smoke.py`
- Capture stdout/stderr to `logs/smoke-<timestamp>.log`.
- Exit code 0 → proceed.
- Exit code non-zero → **stop**, publish failed checks list, suggest fix commands.

### 3.3 Optional Lint / Format
- If `ruff` or `pylint` are available, run:
  - `ruff check src/`
  - `python -m py_compile src/dxfvec/*.py`
- Report warnings but do not block deployment on warnings alone.

---

## 4. Build

**Goal:** produce a tested artifact ready for deployment.

### 4.1 Docker Build (primary artifact)
- Run: `docker build -t dxfvec:ci-<short-sha> .`
- Tag also as `dxfvec:latest` only on main-branch successful builds.
- If build fails:
  - Capture Docker build logs to `logs/docker-build-<timestamp>.log`.
  - **stop** pipeline.
  - Emit diagnostic summary:
    - base image digest
    - failing Dockerfile step
    - suggested fix (e.g., missing apt packages, network timeout during pip install)

### 4.2 Docker Sanity Check
- Run a short-lived container that only imports the package:
  - `docker run --rm dxfvec:ci-<short-sha> python -c "import dxfvec; print(dxfvec.__version__)"`
- If import fails inside container: **fail** build even if `docker build` succeeded.

---

## 5. Deployment

**Goal:** deploy to the configured target with automatic fallback where possible.

### 5.1 Target Detection
- Choose deploy target in this priority order:
  1. Explicit `DEPLOY_TARGET` env var (`render | vercel | railway | fly | docker`)
  2. Presence of platform-specific config:
     - `render.yaml` → `render`
     - `vercel.json` → `vercel`
  3. Default → `docker` (local or registry-pushed image)

### 5.2 Render (render.yaml)
- Pre-requisites: `render` CLI or GitHub integration.
- Steps:
  1. Push image to a registry if required by Render (Docker-based services).
  2. Run `render services deploy dxfvec` or equivalent.
  3. Capture service URL from Render output/config.
- Failure handling:
  - If build or deploy command exits non-zero: **stop**.
  - Parse Render error message:
    - build failure → attach `logs/render-build-<timestamp>.log`
    - quota exceeded → advise waiting or upgrading plan
    - health check timeout → advise increasing start timeout in Dockerfile CMD

### 5.3 Vercel (vercel.json)
- Pre-requisites: `vercel` CLI, project linked.
- Steps:
  1. Run `vercel pull --yes --environment=production`
  2. Run `vercel build --prod`
  3. Run `vercel deploy --prebuilt --prod`
- Failure handling:
  - If build fails → capture `logs/vercel-build-<timestamp>.log`
  - If deploy fails → capture `logs/vercel-deploy-<timestamp>.log`
  - If Python runtime unsupported → advise adjusting `vercel.json` Python version or using Render instead.

### 5.4 Railway / Fly.io
- If CLI detected and logged in:
  - Railway: `railway up`
  - Fly.io: `fly deploy`
- Capture full CLI output to `logs/<platform>-deploy-<timestamp>.log`.
- On failure:
  - auth errors → remind to run login command
  - quota errors → advise adding credit or pausing
  - build errors → same logic as Docker build failures

### 5.5 Local Docker
- Run: `docker-compose up -d`
- Failure handling:
  - port conflict (5000 already in use) → suggest `DOCKER_PORT` override
  - container crash → `docker logs dxfvec-dxfvec-1` → attach to logs

---

## 6. Post-Deployment Verification

**Goal:** confirm the deployed service is actually usable.

### 6.1 Health Check
- Run `curl -f http://<service-url>/health` with timeout 30s, retries 5, backoff 2s.
- Expected JSON: `{"status":"ok","service":"dxfvec",...}`.
- If health check fails after retries:
  - **mark deployment as suspect**
  - collect:
    - service URL
    - request logs / container logs
    - health-check command and stderr
  - if auto-rollback is configured: rollback to previous known-good release.
  - if no rollback: append `NEEDS_MANUAL_INTERVENTION` marker to log.

### 6.2 Functional Smoke Test (remote)
- Run against deployed URL:
  - `POST /convert` with a tiny valid image payload.
  - Expect HTTP 200 JSON with `filename` and `stats` fields.
- If endpoint returns non-200:
  - expected 4xx → capture JSON error → likely config/code bug.
  - expected 5xx → capture stack trace in logs → likely runtime/env issue.
- If upload size exceeded or timeout: log exact error and adjust limits.

### 6.3 Quick Regression Check
- Use `evals/case-01/test_drawing.png` (auto-generated if missing via `evals/case-01/generate_test.py`).
- Run the same conversion command/logic against the live service.
- Compare result structure (DXF produced, non-empty ZIP, review.md inside).
- If output structure is wrong: **fail verification**, capture response and file listing.

### 6.4 URL & Reachability
- Record final public URL.
- If target is Render/Railway/Fly: capture CLI-generated URL.
- If target is Vercel: capture deployment URL from `vercel inspect` if needed.
- Print reachable URLs and paths to:
  - `/` (web UI)
  - `/health`
  - `/api/ping`
  - `/api/engines`
  - `/api/presets`
  - `/api/providers`

---

## 7. Error Handling & Reporting

### 7.1 Failure Categories
- **Pre-flight fail**: stop immediately, summarize missing files/env.
- **Install fail**: stop, emit pip/system hint, do not run tests.
- **Test fail**: stop, attach `test_smoke.py` output, do not deploy.
- **Build fail**: stop, attach Docker logs, do not deploy.
- **Deploy fail**: stop, attach deploy logs, do not run post-deploy verification.
- **Post-deploy fail**: mark deployment as suspect, attempt rollback if configured.

### 7.2 Logging
- Write all logs to `logs/<step>-<timestamp>.<ext>` under the project root.
- Never print raw secrets to logs. Mask values that match:
  - `DXVEC_*`
  - `API_KEY`
  - `SECRET`
  - `TOKEN`
  - Bearer tokens

### 7.3 Exit Codes
- `0` — success, deployment healthy.
- `1` — pre-flight/install/test/build/deploy/post-deploy failure.
- `2` — configuration or environment error (e.g., missing secrets when required).

---

## 8. Autonomous Loop Behavior

When used as an autonomous workflow inside OpenCode:

### 8.1 Idempotency
- Each step checks for prior completion artifacts before running:
  - `.cache/install-done`
  - `.cache/build-done-<target>`
  - `.cache/deploy-done-<target>`
- Re-running the workflow skips already-successful steps unless explicitly forced.

### 8.2 Human-in-the-Loop Gates
- **Deploy gate**: stop before deploying to production unless `DEPLOY_AUTO_APPROVE=true`.
- **Rollback gate**: if a post-deploy check fails, do not chain another deploy without either:
  - explicit approval, or
  - automatic rollback to the last known-good release.

### 8.3 Observability
- Emit a concise machine-readable summary to `logs/workflow-summary-<timestamp>.json`:
  - `sha`
  - `timestamp`
  - `target`
  - `steps`
  - `failed_step`
  - `deploy_url`
  - `health_url`
  - `verification_status`

---

## 9. Local Quickstart (fallback)

If platform deployment is not configured, the workflow should default to local Docker verification:

```bash
docker-compose up -d
curl -f http://localhost:5000/health
```

If even local Docker is unavailable, the workflow should fall back to:

```bash
python -m dxfvec.web
```

and run the smoke tests against `http://localhost:5000`.

---

*Workflow version: 1.0.0*  
*Last updated: 2026-07-01*
