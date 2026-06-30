# NEXT-DIRECTIONS — dxf-vectorizer

Planned releases. Each item: what / why deferred / how.

---

## Done (v0)

### Gemini provider — tested ✅
**What:** Pipeline works end-to-end with `gemini-2.5-flash` via LiteLLM.
**How:** `dxfvec convert test.png --provider google`
**Note:** `gemini-1.5-pro` is deprecated (404); updated to `gemini-2.5-flash`.

### DXF writer fix — validated ✅
**What:** Fixed `ezdxf` linetype API bug; CUT/BEND/DIM layers produce valid DXF.
**How:** `ezdxf.readfile()` passes on all outputs.

---

## v1

### Scale calibration
**What:** User provides one known measurement ("this hole is 20mm in reality") → calibrate pixel-to-mm ratio → dimensionally accurate DXF.
**Why deferred:** v0 proves geometry extraction quality first; scale needs a second input field and a calibration step.
**How:** `--scale "64px=20mm"` CLI flag → compute ratio → apply to all coordinates before writing DXF.

### OpenAI GPT-4o provider (tested)
**What:** Confirm pipeline works with GPT-4o vision.
**Why deferred:** No OPENAI_API_KEY on hand; same LiteLLM routing, just needs validation.
**How:** `OPENAI_API_KEY=sk-... dxfvec convert test.png --provider openai`

### Batch mode (multiple images)
**What:** Process a folder of drawings and output a ZIP of DXF files.
**Why deferred:** v0 establishes single-image quality; batch adds complexity.
**How:** `dxfvec batch ./drawings/ --provider google --output-dir ./results/` — loop over files, bundle into ZIP.

### Ollama/LLaVA local provider (tested)
**What:** Run entirely offline with no API key — useful for shop-floor machines without internet.
**Why deferred:** Needs Ollama installed locally; no API key needed.
**How:** `ollama run llava` then `dxfvec convert test.png --provider ollama`

### Multi-agent CrewAI mode
**What:** 3-agent chain (Vision Analyst → DXF Builder → QA Reviewer) for higher-quality output.
**Why deferred:** crewai has Python 3.14 compatibility issues; optional `[crew]` extra.
**How:** `pip install -e ".[crew]"` then `dxfvec convert test.png --provider google --mode crew`

---

## v2

### CMA cloud deployment
**What:** Run as a Claude Managed Agent — users upload drawings via API, get DXF back.
**Why deferred:** Needs ANTHROPIC_API_KEY; standalone CLI validates the core logic first.
**How:** LAUNCH.md steps (environment → agent → session → kickoff).

### Per-customer deployment (productize)
**What:** Each customer uploads drawings via their own interface; isolated vault credentials.
**Why deferred:** Needs a UI layer + vault-per-user pattern; out of scope for internal tooling.
**How:** CMA vault-per-user pattern (`external_user_id` in session metadata, one vault per customer).

### SVG preview + G-code export
**What:** Output an SVG overlay showing detected geometry, and a G-code file for direct CNC use.
**Why deferred:** Needs `svgwrite` (SVG) and a CAM library (G-code); adds scope beyond v0.
**How:** `pip install svgwrite` + ezdxf→SVG converter; G-code via `ezdxf.addons.r12writer`.

### Confidence-gated human-in-the-loop review
**What:** When confidence is "low", pause and ask the engineer to confirm ambiguous elements.
**Why deferred:** Needs a surface that can surface `requires_action` confirmations.
**How:** Custom tool `request_human_review(ambiguities=[...])` → `requires_action` → engineer answers.

### Network lock-down
**What:** Restrict the environment to only PyPI after packages are cached.
**Why deferred:** Hardening — unrestricted is fine while the agent is only doing local image processing.
**How:** Switch environment to `networking: limited` + `allowed_hosts: ["pypi.org"]`.
