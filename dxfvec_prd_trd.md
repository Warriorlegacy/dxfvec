---
title: "dxfvec — Product & Technical Requirements"
subtitle: "PRD + TRD for an Industry-Grade Image Vectorization & DXF Conversion Platform"
author: "Prepared for: dxfvec.onrender.com"
date: "July 2026"
---

\newpage

# 0. Document Control

| Field | Value |
|---|---|
| Product | dxfvec — Image Vectorization & DXF Conversion Tool |
| Document type | Combined Product Requirements Document (PRD) + Technical Requirements Document (TRD) |
| Reference implementation reviewed | https://dxfvec.onrender.com/ (Classic/local trace, VTracer "Advanced", BYOK cloud engines: Vectorizer.AI, DXFai; DXF modes Lines/Hatch/Faces; presets Logo Engrave, Laser Stencil, Technical Drawing, Contour Map) |
| Status | Draft v1.0 for engineering planning |
| Owner | Product/Founder |

---

\newpage

# PART A — PRODUCT REQUIREMENTS DOCUMENT (PRD)

## 1. Executive Summary and Success Criteria

### 1.1 Problem statement
The current tool already covers the right *shape* of the problem — raster upload, an engine selector (Classic local trace vs. VTracer vs. BYOK cloud APIs), a DXF mode selector (Lines/Hatch/Faces), presets, and expert parameters (threshold, smoothing, corner sensitivity, noise filter, min contour area). What is missing is **industry-grade reliability of the output**: dimensionally accurate, CAD-clean, layer-correct DXF files that a laser cutter, CNC router, or CAD engineer can trust without manual cleanup. Today's gap is typically not "does it trace a shape" but:

- Inconsistent path smoothness (jagged or over-simplified curves depending on threshold).
- Open contours / gaps that break closed-loop requirements for cutting.
- No reported or enforced dimensional/scale accuracy (px→mm/inch calibration).
- No verification step confirming the DXF is valid, closed, and importable in AutoCAD/Fusion 360/LightBurn.
- No visibility into confidence/error metrics so the user knows whether to trust the output.

### 1.2 Vision
Make dxfvec the **default free tool a mechanical engineer, sign maker, or laser-cutting hobbyist reaches for** when they need a raster logo, scan, or photo turned into a dimensionally accurate, CAD-ready DXF — with the transparency and controls of a paid tool (Vector Magic, Vectorizer.AI, Adobe Illustrator Image Trace) but zero cost and no lock-in.

### 1.3 Goals (12-month horizon)
1. **Fidelity**: ≥95% of "clean" test inputs (logos, line art, scanned technical drawings) produce a DXF that opens without repair warnings in AutoCAD, Fusion 360, and LibreCAD.
2. **Accuracy**: Dimensional error ≤0.5% (or a user-defined tolerance) between the calibrated raster measurement and the exported DXF geometry.
3. **Trust**: Every export includes a machine-readable QA report (entity count, open-path count, self-intersections, bounding box, units) surfaced in the UI before download.
4. **Throughput**: Batch mode processes ≥20 images per job without manual re-entry of settings.
5. **Adoption**: Reduce "re-upload after failed DXF import" support/feedback incidents by 80% versus current baseline (to be measured once analytics are in place).

### 1.4 Success metrics (KPIs)

| Metric | Definition | Target (MVP) | Target (V1 GA) |
|---|---|---|---|
| Import success rate | % of exported DXFs opened without error in AutoCAD/Fusion/LibreCAD (via automated import test harness) | ≥90% | ≥98% |
| Closed-path integrity | % of intended-closed contours exported as closed LWPOLYLINE/POLYLINE with zero gap | ≥95% | ≥99.5% |
| Dimensional accuracy | Deviation between calibrated real-world size and exported bounding geometry | ≤1% | ≤0.5% |
| Node efficiency | Average nodes/mm of curve vs. baseline Potrace/VTracer output (lower = cleaner, must not sacrifice accuracy) | -20% vs. uncontrolled trace | -35% |
| P95 processing latency | Single image, ≤10MP, Classic/Advanced engine | ≤8s | ≤4s |
| Batch throughput | Images/minute in batch queue (server-side, 2 vCPU baseline) | 6/min | 15/min |
| Error transparency | % of exports accompanied by a QA report the user can inspect | 100% (MVP requirement) | 100% |

### 1.5 Non-goals (explicitly out of scope for V1)
- Full 3D solid modeling / STEP export.
- Native DWG *write* support (DWG read-only via BYOK cloud passthrough only, if at all — DWG is a closed Autodesk binary format; DXF remains the primary open interchange target).
- Real-time collaborative editing of vector output (single-user session model for V1).
- Mobile native apps (responsive web only).

---

## 2. User Personas and Scenarios

| Persona | Profile | Primary need | Representative scenario |
|---|---|---|---|
| **Priya, Mechanical/Product Design Engineer** | Uses Fusion 360/SolidWorks daily; occasionally needs to digitize a hand sketch or scanned part outline into CAD | Dimensional accuracy, closed loops, correct units, minimal cleanup | Uploads a scanned bracket sketch, sets a known reference dimension for calibration, exports DXF at 1:1 scale in mm, imports directly into Fusion 360 sketch. |
| **Arjun, Laser-cutting / Sign-making Hobbyist/SMB owner** | Runs a desktop laser cutter (LightBurn); needs cut/engrave separation | Layer separation (CUT vs. ENGRAVE), closed vector paths, fast turnaround, batch processing of a product catalog | Uploads 15 logo PNGs, applies the "Laser Stencil" preset in batch, gets a ZIP of DXFs with CUT and ENGRAVE layers correctly separated, loads directly into LightBurn. |
| **Meera, Graphic Designer / Sign Shop Operator** | Needs vector versions of raster logos for vinyl cutting or large-format printing | Color/layer fidelity, smooth curves matching the original artwork, SVG *and* DXF export | Uploads a client's low-res logo PNG, uses AI Enhance + Advanced (VTracer) engine, exports both SVG (for print) and DXF (for the vinyl cutter), checks color-to-layer mapping. |
| **Devesh, CNC/Manufacturing Technician** | Needs precise outlines of mechanical parts from photos of templates or existing parts for CNC routing | Node reduction (clean G-code later), tolerance control, verification that all paths are closed before sending to CAM software | Photographs a physical template on a grid background, uses Auto-Correct Perspective + calibration, exports DXF with a QA report confirming zero open paths before sending to CAM. |
| **Anita, Student / Hobbyist (non-CAD-literate)** | First-time user, no CAD background | Simple, guided experience; sensible defaults; doesn't want to tune 6 sliders | Uploads a coloring-book style image, picks the "Logo Engrave" preset, downloads DXF without touching expert settings. |

### 2.1 Key end-to-end scenario (critical path)
1. User uploads image (drag/drop or file picker).
2. Tool shows a live preview with an editable trace overlay.
3. User selects engine (Classic/Advanced/Cloud BYOK), preset, and optionally sets a **calibration reference** (e.g., "this line = 50 mm") for real-world scale accuracy.
4. User adjusts expert settings if needed, with live re-preview (debounced, non-blocking).
5. User reviews a **QA panel**: entity count, open/closed path count, self-intersection warnings, estimated dimensional accuracy.
6. User exports DXF (and/or SVG/PDF), receives a downloadable file plus the QA report inline.
7. (Batch) User uploads a folder/ZIP, applies one settings profile to all, receives a ZIP of outputs + a CSV/JSON summary QA report per file.

---

## 3. Feature List with Prioritization

Priority key: **P0** = MVP blocker, **P1** = V1 GA, **P2** = fast-follow, **P3** = future/backlog.

### 3.1 Input & preprocessing

| Feature | Priority | Notes |
|---|---|---|
| Multi-format raster input: PNG, JPG, WEBP, BMP, TIFF | P0 | Already present; add HEIC (P2) for mobile photo uploads |
| Drag/drop + click-to-browse + paste-from-clipboard | P0 | Paste is a P1 add |
| Auto-deskew / perspective correction ("Auto-Correct Perspective") | P0 | Already present; needs accuracy validation against a checkerboard/reference-grid test set |
| Manual 4-point perspective correction (fallback when auto fails) | P1 | Critical for photographed parts on non-flat surfaces |
| Denoise / sharpen / rotate / resize | P0 | Already present |
| Background removal (flat-color / AI matting) | P1 | Common blocker for photographed objects |
| **Calibration tool**: user draws a reference line and enters its real-world length/unit | **P0** | This is the single highest-leverage feature for "industry-grade" — without it, DXF output has no trustworthy scale |
| Color quantization control (posterize levels) for multi-color source art | P1 | Needed for layer/color fidelity goal |

### 3.2 Vectorization engines

| Feature | Priority | Notes |
|---|---|---|
| Classic (local, fast) trace engine | P0 | Existing; document algorithm (contour tracing + Douglas-Peucker) |
| Advanced (VTracer) engine | P0 | Existing; expose VTracer's native params (filter_speckle, color_precision, corner_threshold, splice_threshold) via the "expert settings" UI rather than hiding them |
| Cloud BYOK: Vectorizer.AI | P1 | Keep BYOK model (user's own API key, never stored server-side in plaintext) |
| Cloud BYOK: DXFai / equivalent | P1 | Same BYOK model |
| Centerline vs. outline tracing mode | P0 | Critical differentiator: outline tracing (default, good for filled logos/stencils) vs. centerline tracing (essential for line-art, hand sketches, single-stroke engraving) — this is a common failure mode of naive tracers |
| Hybrid mode: ML-based edge detection (e.g., a lightweight learned edge model) pre-pass before classic contour trace, for noisy photo input | P2 | Improves quality on real-world photographed input vs. clean scans |

### 3.3 Vector accuracy & cleanup controls

| Feature | Priority | Notes |
|---|---|---|
| Threshold / binarization control | P0 | Existing |
| Smoothing / corner sensitivity sliders | P0 | Existing; add live numeric readout of resulting node count |
| Min contour area (noise filter) | P0 | Existing |
| **Tolerance-based node reduction** (Douglas-Peucker / Visvalingam with explicit ε in real-world units, not just an abstract slider) | **P0** | Needed so "smoothing" has a defined geometric meaning (max deviation in mm) rather than a black-box 0–100 slider |
| **Curve fitting**: arcs/circles detection and Bezier→arc conversion for CAD-native entities (ARC, CIRCLE) instead of only polylines | **P0** | Industry-grade DXF for CNC/laser should represent true circles/arcs as ARC/CIRCLE entities, not polygon approximations — this materially affects machining quality and file size |
| Gap closing (bridge small breaks in traced strokes) | P0 | Existing as "AI Enhance"; needs a configurable max-gap-distance parameter |
| Self-intersection detection & auto-repair | P0 | Must flag/report even if auto-repair is imperfect |
| Closed-loop enforcement for CUT layers | P0 | A cut path that isn't closed is a hard failure for laser/CNC use |
| Manual node editing (drag/add/delete nodes) post-trace | P1 | High engineering effort; large value for "final 5% cleanup" |
| Undo/redo for manual edits | P1 | Required once manual editing exists |

### 3.4 DXF/CAD export

| Feature | Priority | Notes |
|---|---|---|
| DXF export: Lines (cut paths), Hatch (engrave fills), Faces (closed shapes) | P0 | Existing modes; validate each against real CAM/laser software |
| Layer mapping (CUT/ENGRAVE/BEND/DIM as named DXF layers with distinct colors) | P0 | Existing; formalize a documented layer-naming convention (Section 5.4) |
| DXF version selection (R12/AC1009 for max compatibility; R2010/AC1024 for hatch/spline-rich output) | **P0** | Different downstream tools need different DXF versions; this must be explicit, not hidden |
| Units declaration in DXF header ($INSUNITS) matching the user's calibration | **P0** | Currently a likely silent-failure point; must be explicit and correct |
| Real ARC/CIRCLE/ELLIPSE entities (not polyline approximation) where curve fitting detects them | P0 | See 3.3 |
| SVG export (in addition to DXF) | P0 | Existing implied via web preview; make it a first-class export option |
| PDF export (vector, for print/reference) | P1 | |
| DWG export (via BYOK cloud conversion only, e.g., ODA/Autodesk-licensed converter) | P2 | DWG is closed-spec; do not attempt a from-scratch writer |
| Output file integrity / validator report (entity count, closed/open path count, layer list, bounding box, DXF audit pass/fail) | **P0** | This is the "output verification" requirement — non-negotiable for the industry-grade goal |
| Downloadable QA report (JSON + human-readable summary) alongside the DXF | P0 | |

### 3.5 Batch processing

| Feature | Priority | Notes |
|---|---|---|
| Multi-file upload / ZIP upload | P0 | |
| Apply one settings profile across a batch | P0 | |
| Per-file override within a batch | P1 | |
| Batch job queue with progress + partial-failure handling | P0 | A single bad image must not fail the whole batch |
| Batch output as ZIP + summary CSV/JSON report | P0 | |
| Saved presets (user-named, beyond the 4 built-ins) | P1 | |

### 3.6 UX / trust / transparency

| Feature | Priority | Notes |
|---|---|---|
| Live before/after overlay (raster vs. trace) with opacity slider | P0 | |
| Real-time re-preview on parameter change (debounced) | P0 | |
| QA panel (see 3.4) surfaced before download, not just in the file | P0 | |
| Side-by-side vector inspector (zoomable, shows node points) | P1 | |
| Shareable/persistent result links (already implied by "Gallery") | P1 | Ensure privacy controls — see Section 7 |
| Guided mode ("I don't know what these settings mean") vs. Expert mode toggle | P1 | Serves Persona Anita vs. Persona Priya |

### 3.7 MVP scope cut (explicit)
MVP = all **P0** items above. This is the minimum bar to credibly claim "industry-grade": calibration, tolerance-defined smoothing, arc/circle detection, correct DXF units/version/layers, closed-path enforcement, and a verification report. Everything else is V1 GA or later.

---

## 4. UX Flows and Wireframe-Level Descriptions

### 4.1 Primary flow: Single-image vectorize → DXF

```
┌─────────────────────────────────────────────────────────┐
│ Step 1: Upload                                           │
│  [ Drag & drop / Browse ]  →  Thumbnail + file metadata   │
│  (dimensions, DPI if present, file size)                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Step 2: Preprocess                                        │
│  Rotate | Deskew | Auto-Perspective | Denoise | Sharpen    │
│  Live thumbnail updates                                    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Step 3: Calibrate (NEW — P0)                               │
│  "Draw a line over a known dimension"                      │
│  [Canvas with draggable calibration line]                  │
│  Length: [____] Unit: [mm ▾]                                │
│  Skip → defaults to px-based export, flagged in QA report   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Step 4: Engine & Mode                                       │
│  Engine: (•) Classic  ( ) Advanced/VTracer  ( ) Cloud BYOK   │
│  Trace mode: (•) Outline  ( ) Centerline                     │
│  DXF Mode: [Lines ▾]  Preset: [Custom ▾]                     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Step 5: Expert Settings (collapsible)                        │
│  Threshold ──●────── 127                                     │
│  Tolerance (mm) [0.10]   ← replaces abstract "smoothing"      │
│  Corner sensitivity ──●──                                     │
│  Min contour area (mm²) [_]                                   │
│  Noise filter ──●──                                             │
│  ☑ AI Enhance   ☑ Auto-Correct Perspective                     │
│  ☑ Detect arcs/circles                                         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Step 6: Live Preview                                          │
│  [Raster | Overlay slider | Vector]  Zoom/Pan                 │
│  Node count: 342   Est. accuracy: ±0.3mm                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Step 7: QA Report (blocking gate before export — P0)           │
│  ✅ 3 closed paths   ⚠ 1 open path (2.1mm gap) — [Auto-fix]      │
│  ✅ Units: mm, DXF version R2010     ✅ No self-intersections     │
│  [ Export DXF ]  [ Export SVG ]  [ Export PDF ]                  │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Batch flow

```
Upload ZIP/multi-file → Choose/confirm shared settings profile
   → Queue view (per-file status: queued/processing/done/failed)
   → Per-file QA summary (pass/warn/fail badge)
   → Download all (ZIP) + summary.csv + summary.json
```

### 4.3 Error/edge-case flows
- **Unsupported/corrupt file** → inline error, does not block other files in a batch.
- **Trace produces zero contours** (e.g., blank or nearly-uniform image) → explicit empty-state message with suggested threshold adjustment, not a silent empty DXF.
- **Image exceeds size/resolution limit** → offer auto-downscale with a warning, or reject with a clear limit stated (see NFRs).
- **QA report shows open paths** → user can choose "Auto-fix (bridge gaps)" or "Export anyway" (with the warning embedded in the DXF as a comment/metadata layer) — never silently pass off unclosed paths as clean.

---

## 5. Data Model and API Specs

### 5.1 Core entities

```
Job
 ├─ id (uuid)
 ├─ status: queued | processing | done | failed
 ├─ created_at, completed_at
 ├─ input: Asset
 ├─ settings: TraceSettings
 ├─ calibration: Calibration | null
 ├─ outputs: [Asset]  (dxf, svg, pdf)
 ├─ qa_report: QAReport
 └─ engine_used: classic | vtracer | vectorizer_ai | dxfai

Asset
 ├─ id (uuid)
 ├─ kind: raster_input | svg_output | dxf_output | pdf_output
 ├─ storage_url (signed, expiring)
 ├─ mime_type, size_bytes, checksum_sha256
 └─ width_px, height_px (for raster)

Calibration
 ├─ reference_px_length: float
 ├─ real_world_length: float
 ├─ unit: mm | cm | in | px
 └─ scale_factor: float   (derived: real_world_length / reference_px_length)

TraceSettings
 ├─ engine: classic | vtracer | vectorizer_ai | dxfai
 ├─ trace_mode: outline | centerline
 ├─ threshold: int (0–255)
 ├─ tolerance_mm: float          (replaces raw "smoothing" 0–100)
 ├─ corner_sensitivity: float (0–1)
 ├─ min_contour_area_mm2: float
 ├─ noise_filter: float (0–1)
 ├─ ai_enhance: bool
 ├─ auto_perspective: bool
 ├─ detect_arcs: bool
 ├─ dxf_mode: lines | hatch | faces
 ├─ dxf_version: R12 | R2010 | R2018
 └─ preset: custom | logo_engrave | laser_stencil | technical_drawing | contour_map

QAReport
 ├─ entity_count: int
 ├─ closed_path_count: int
 ├─ open_path_count: int
 ├─ open_path_locations: [{x, y, gap_mm}]
 ├─ self_intersections: [{x, y}]
 ├─ bounding_box: {min_x, min_y, max_x, max_y, unit}
 ├─ estimated_dimensional_accuracy_pct: float
 ├─ dxf_audit_pass: bool           (ezdxf doc.audit() result, zero critical errors)
 ├─ layers: [{name, entity_count, color_aci}]
 └─ warnings: [string]
```

### 5.2 REST API (V1)

Base URL: `https://api.dxfvec.example/v1`

#### `POST /jobs`
Create a vectorization job.

**Request (multipart/form-data)**
```
file: <binary image>
settings: {
  "engine": "vtracer",
  "trace_mode": "outline",
  "threshold": 127,
  "tolerance_mm": 0.15,
  "corner_sensitivity": 0.5,
  "min_contour_area_mm2": 1.0,
  "noise_filter": 0.3,
  "ai_enhance": true,
  "auto_perspective": false,
  "detect_arcs": true,
  "dxf_mode": "lines",
  "dxf_version": "R2010",
  "preset": "laser_stencil"
}
calibration: {
  "reference_px_length": 342.5,
  "real_world_length": 50.0,
  "unit": "mm"
}
```

**Response `202 Accepted`**
```json
{
  "job_id": "8f14e45f-ceea-467e-9f2d-8bf1a6c2b3d1",
  "status": "queued",
  "poll_url": "/v1/jobs/8f14e45f-ceea-467e-9f2d-8bf1a6c2b3d1"
}
```

#### `GET /jobs/{job_id}`
```json
{
  "job_id": "8f14e45f-ceea-467e-9f2d-8bf1a6c2b3d1",
  "status": "done",
  "engine_used": "vtracer",
  "outputs": {
    "dxf": "/v1/jobs/8f14.../download?format=dxf",
    "svg": "/v1/jobs/8f14.../download?format=svg"
  },
  "qa_report": {
    "entity_count": 47,
    "closed_path_count": 12,
    "open_path_count": 0,
    "self_intersections": [],
    "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 120.4, "max_y": 88.2, "unit": "mm"},
    "estimated_dimensional_accuracy_pct": 99.6,
    "dxf_audit_pass": true,
    "layers": [
      {"name": "CUT", "entity_count": 12, "color_aci": 1},
      {"name": "ENGRAVE", "entity_count": 35, "color_aci": 3}
    ],
    "warnings": []
  }
}
```

#### `POST /jobs/batch`
Same settings object applied to a ZIP or multi-file array. Returns a `batch_id` with per-file sub-job polling.

#### `GET /jobs/{job_id}/download?format=dxf|svg|pdf`
Returns the binary file with `Content-Disposition: attachment`.

#### `POST /jobs/{job_id}/autofix`
Applies gap-closing/self-intersection repair to a completed job's geometry and returns a new QA report without re-running the full trace.

### 5.3 Validation rules

| Input | Rule |
|---|---|
| File type | MIME-sniffed (not extension-trusted) against PNG/JPEG/WEBP/BMP/TIFF |
| File size | ≤25 MB per image (MVP); configurable per deployment |
| Resolution | ≤40 MP; images above are auto-downscaled with a warning, not silently processed |
| `threshold` | int, 0–255 |
| `tolerance_mm` | float, >0, ≤10 (sane upper bound to prevent degenerate geometry) |
| `calibration.reference_px_length` | float, >0 |
| `calibration.real_world_length` | float, >0 |
| `dxf_version` | enum, one of `R12`, `R2010`, `R2018` |
| Batch size | ≤50 files or ≤250MB combined (MVP) |
| API key (BYOK cloud engines) | Never persisted in plaintext; encrypted at rest, used once per job, purge option exposed to user |

### 5.4 DXF layer-naming convention (formalized)

| Layer name | ACI color | Purpose |
|---|---|---|
| `CUT` | 1 (red) | Through-cut paths, always closed polylines |
| `ENGRAVE` | 3 (green) | Fill/hatch regions for engraving |
| `BEND` | 5 (blue) | Fold/bend lines (sheet metal use case) |
| `DIM` | 7 (white/black) | Dimension annotations, non-cut reference geometry |
| `SCRAP` / `WASTE` | 8 (gray) | Optional: material to be removed, for nested-cut workflows |

---

## 6. Success Criteria Recap (Acceptance View)

A release is considered **industry-grade GA-ready** when, on a fixed regression test corpus (≥50 images spanning logos, scanned line art, photographed parts, multi-color designs):
- ≥98% of exports pass automated DXF audit (`ezdxf.audit()` zero critical errors) and open cleanly in AutoCAD, Fusion 360, and LibreCAD.
- ≥99.5% of intended-closed contours are exported closed.
- Dimensional error ≤0.5% against calibrated ground truth on ≥95% of calibrated jobs.
- Every job produces a QA report, and no job with `open_path_count > 0` or `dxf_audit_pass: false` is presented to the user as "success" without an explicit warning state.

\newpage

# PART B — TECHNICAL REQUIREMENTS DOCUMENT (TRD)

## 7. Architecture Overview

### 7.1 System components

```
┌────────────┐     ┌───────────────────┐     ┌────────────────────┐
│  Web Client│────▶│  API Gateway / BFF │────▶│  Job Queue (Redis/  │
│ (Next.js)  │◀────│  (FastAPI)         │◀────│  RQ or Celery)      │
└────────────┘     └───────────────────┘     └─────────┬───────────┘
                                                          │
                     ┌────────────────────────────────────┼─────────────────────┐
                     ▼                                    ▼                     ▼
           ┌──────────────────┐                ┌──────────────────┐  ┌──────────────────┐
           │ Preprocessing     │                │ Vectorization     │  │ DXF/SVG Export &  │
           │ Worker            │───────────────▶│ Worker            │─▶│ Verification Worker│
           │ (OpenCV pipeline) │                │ (Classic/VTracer/ │  │ (ezdxf + audit)    │
           │                   │                │  BYOK cloud proxy)│  │                    │
           └──────────────────┘                └──────────────────┘  └──────────────────┘
                     │                                    │                     │
                     └────────────────────────────────────┴─────────────────────┘
                                                          │
                                                          ▼
                                              ┌──────────────────────┐
                                              │ Object Storage (S3/  │
                                              │ R2), signed URLs      │
                                              └──────────────────────┘
                                                          │
                                                          ▼
                                              ┌──────────────────────┐
                                              │ Metadata DB (Postgres)│
                                              │ Jobs, QAReports, Users│
                                              └──────────────────────┘
```

### 7.2 Recommended tech stack

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | Next.js (React) + Canvas/SVG-based interactive preview (or a lightweight WebGL canvas for large images) | Matches Golu's existing stack; SSR for fast first paint; client-side canvas for live overlay/calibration UI |
| API layer | FastAPI (Python) | Matches existing stack choices; async I/O for job orchestration; automatic OpenAPI schema generation for the API spec in Section 5.2 |
| Job queue | Redis + RQ (simpler) or Celery (if multi-queue priority needed for batch vs. single-image) | Decouples upload from potentially multi-second trace/export work; enables horizontal worker scaling |
| Image preprocessing | OpenCV (Python) | Deskew, perspective transform, denoise (bilateral filter), adaptive threshold |
| Classic trace engine | Potrace (via `pypotrace` or subprocess) or a custom contour-tracing (`cv2.findContours`) + Douglas-Peucker simplification pipeline | Fast, deterministic, good for clean binary/line-art input |
| Advanced trace engine | VTracer (Rust core, via CLI or `vtracer` Python bindings) | Already in use; supports color clustering, good default quality |
| Centerline tracing | `autotrace` or a skeletonization pipeline (`skimage.morphology.skeletonize` + graph-based path extraction) | Needed for the P0 centerline mode (Section 3.2) |
| Arc/circle fitting | Custom: RDP-simplified polyline segments tested against circular-arc fit (least-squares circle fit, e.g. via `scipy.optimize`) with a max-deviation acceptance threshold | Converts polyline approximations of curves into true DXF ARC/CIRCLE entities |
| DXF read/write/validation | **ezdxf** (Python) | Actively maintained, pure-Python, supports `doc.audit()` for integrity validation — this is the backbone of the "output verification" requirement |
| SVG generation | `svgwrite` or direct construction from the same internal path representation used for DXF (single source of truth — see 7.3) | Avoids divergence between SVG and DXF outputs |
| PDF export | ReportLab (vector drawing from the same path model) | Consistent with existing PDF tooling experience |
| Object storage | S3-compatible (AWS S3, Cloudflare R2, or Backblaze B2 for cost) | Signed, expiring URLs; lifecycle policy to auto-delete after N days for privacy/cost |
| Metadata DB | PostgreSQL (Supabase acceptable given existing stack familiarity) | Jobs, QA reports, user API-key references (encrypted), batch summaries |
| Cloud BYOK proxy | Thin server-side proxy that forwards to Vectorizer.AI / DXFai using the user-supplied key, never logging the key in plaintext, key held in memory for the request lifetime only | Avoids storing third-party credentials at rest unless the user explicitly opts into "remember my key" (encrypted, revocable) |
| Deployment | Containerized (Docker) workers behind the existing Render deployment, or migrate compute-heavy workers to a provider with better cold-start/CPU profile (e.g., Fly.io, Railway, or a dedicated GPU/CPU box) if VTracer/OpenCV latency on Render free tier becomes a bottleneck | Render's free/starter tiers have cold starts and limited CPU — worth flagging as a risk (Section 11) |
| Observability | Sentry (errors), OpenTelemetry + a lightweight metrics backend (Grafana Cloud free tier / Prometheus) | Needed to track the KPIs in Section 1.4 in production |

### 7.3 Key architectural principle: single internal path representation

To guarantee SVG, DXF, and PDF exports are *consistent* with each other and with the QA report, the vectorization pipeline should produce **one canonical intermediate geometry model** (e.g., a list of `Path` objects, each a list of typed segments: `Line`, `CubicBezier`, `Arc`, tagged with `layer`, `closed: bool`, `color`) before any format-specific exporter runs. Each exporter (DXF/SVG/PDF) consumes this same model. This avoids the common bug pattern where DXF and SVG outputs subtly disagree because they were generated by separate code paths.

```
Raster Input
   → Preprocessing (OpenCV)
   → Binarization / color segmentation
   → Contour/centerline extraction (engine-specific)
   → Path simplification (tolerance-based, in calibrated real-world units)
   → Arc/circle fitting
   → Canonical PathModel  ◄── single source of truth
   → { DXF exporter, SVG exporter, PDF exporter, QA validator }
```

---

## 8. Performance, Security, and Reliability Requirements

### 8.1 Performance (NFRs)

| Requirement | Target |
|---|---|
| Single-image processing (≤10MP, Classic engine) | P95 ≤ 4s |
| Single-image processing (≤10MP, VTracer/Advanced) | P95 ≤ 8s |
| Live preview re-render on parameter change | ≤500ms perceived latency (debounce input, show stale-preview state while recomputing) |
| Batch job (20 images, Classic engine, 2 vCPU worker) | ≤3 min total |
| API availability | ≥99.5% monthly uptime target |
| Max concurrent jobs per worker pod | Configurable; default 4 (CPU-bound workload — tune based on actual profiling) |
| File upload size | ≤25MB (MVP), chunked upload for future large-format support |

### 8.2 Security

- **Input sanitization**: strict MIME-type sniffing (not filename trust) for uploads; reject polyglot files.
- **No code execution from uploaded content**: image libraries (Pillow/OpenCV) must be kept patched against known CVEs (e.g., historical Pillow decompression-bomb issues) — enforce `Image.MAX_IMAGE_PIXELS` guards.
- **BYOK key handling**: third-party API keys (Vectorizer.AI, DXFai) transmitted over TLS, never logged, held in memory only for the request unless the user opts into encrypted-at-rest storage with a clear delete control.
- **Signed URLs**: all asset downloads via short-lived signed URLs (e.g., 15-minute expiry), not public buckets.
- **Rate limiting**: per-IP and per-API-key rate limits on `/jobs` creation to prevent abuse of the free tier.
- **Data retention & privacy**: uploaded images and outputs auto-deleted after a defined retention window (e.g., 7–30 days) unless the user explicitly saves to a persistent "Gallery" account; the public Gallery feature must have an opt-in (not opt-out) visibility model since users may upload proprietary designs.
- **Dependency hygiene**: automated dependency scanning (Dependabot/Snyk) given reliance on native-code libraries (OpenCV, VTracer's Rust core, potrace bindings).

### 8.3 Reliability
- Job queue with retry-with-backoff for transient worker failures; a job should never silently disappear.
- Idempotent job processing (safe to retry without double-charging BYOK API usage — dedupe on job_id).
- Graceful degradation: if the Advanced (VTracer) engine crashes on a malformed input, fall back to Classic engine with a surfaced warning rather than failing the whole job.
- Circuit breaker around BYOK cloud calls (Vectorizer.AI/DXFai) — timeout and clear error surfaced to the user rather than a hung job.

### 8.4 Accessibility & internationalization
- WCAG 2.1 AA target for the web UI (keyboard navigation for the calibration tool and node editor is the highest-risk area given the canvas-based interaction).
- All units support both metric and imperial (mm/cm and inch), with a persistent user preference.
- UI copy externalized for future localization (i18n-ready string tables), even if only English ships in V1.

---

## 9. Testing Strategy

### 9.1 Test pyramid

| Level | Scope | Example |
|---|---|---|
| **Unit** | Individual pipeline stages | Douglas-Peucker simplification produces ≤ specified max deviation; circle-fit rejects non-circular arcs above residual threshold; DXF layer-color mapping is correct per Section 5.4 |
| **Integration** | Multi-stage pipeline, engine-swappable | Given a fixed input image + settings, Classic and VTracer engines both produce a `PathModel` that passes the QA validator; calibration scale factor correctly propagates from UI input to DXF header units |
| **End-to-end (E2E)** | Full user flow via API and UI | Upload → calibrate → trace → export DXF → verify DXF opens in a headless AutoCAD-compatible validator (e.g., `ezdxf.readfile()` + `doc.audit()`, plus optional ODA File Converter round-trip test) |
| **Golden-file regression** | Fixed corpus of ≥50 representative images (logos, scans, photos, multi-color art) with expected QA report ranges | CI fails if entity count, closed-path %, or dimensional accuracy regresses beyond tolerance vs. last known-good baseline |
| **Cross-tool import validation** | Automated or scripted import test against real CAD/CAM tools | DXF opens without "repair" prompts in AutoCAD (or ODA-based open-source equivalent), Fusion 360 (via API if available), LibreCAD (open-source, scriptable) |
| **Load/performance** | Batch and concurrent job load | 50 concurrent single-image jobs sustain P95 latency targets from Section 8.1 |
| **Security** | Fuzzing, dependency scan | Malformed/oversized image uploads handled gracefully; decompression-bomb guard verified; BYOK key never appears in logs (log-scrubbing test) |

### 9.2 Acceptance criteria examples (Gherkin-style)

```
Feature: Closed-path enforcement for CUT layer

Scenario: A traced logo with a small gap in one contour
  Given an uploaded image with a 2mm gap in one outline stroke
  And AI Enhance gap-closing is enabled with max_gap = 3mm
  When the image is vectorized and exported to DXF
  Then the exported DXF contains zero open paths on the CUT layer
  And the QA report shows open_path_count = 0
  And the DXF audit (ezdxf.audit()) reports zero critical errors

Feature: Dimensional calibration accuracy

Scenario: User calibrates a known 100mm reference line
  Given a calibration line drawn over a reference of known length 100mm
  When the image is vectorized and exported to DXF at scale
  Then the exported DXF bounding box width, when compared to a
    manually measured reference feature, deviates by no more than 0.5%
```

### 9.3 Test data management
Maintain a versioned "golden corpus" repository (separate from the app repo) containing: source raster images, expected `PathModel` snapshots, expected QA report ranges, and reference DXFs opened/validated in at least one real CAD tool per release. Any pipeline change (engine upgrade, tolerance algorithm change) must run against this corpus before merge.

---

## 10. Deployment, Monitoring, and Maintainability Plans

### 10.1 Deployment
- **Environments**: local dev (docker-compose), staging (mirrors prod, used for golden-corpus regression runs), production.
- **CI/CD**: on merge to main — run unit/integration tests, golden-corpus regression, then deploy API + worker containers; frontend deploys independently (e.g., Vercel or same Render/host).
- **Worker scaling**: since vectorization is CPU-bound (contour tracing, VTracer, OpenCV ops), workers should scale horizontally and independently from the API/BFF layer. If staying on Render, use a dedicated worker service tier sized for sustained CPU load rather than the free web-service tier (cold starts and CPU throttling on free tiers are a known risk for this workload).
- **Feature flags**: gate new engines (e.g., ML edge-detection hybrid mode) behind flags for staged rollout.

### 10.2 Monitoring
- **Product KPIs** (Section 1.4) tracked via a metrics pipeline: import success rate, closed-path integrity, dimensional accuracy, P95 latency, batch throughput — computed both on the golden corpus (pre-release) and sampled from real production jobs (post-release, with user consent/anonymization).
- **Operational metrics**: queue depth, worker CPU/memory, job failure rate by engine, BYOK proxy error rate/timeout rate.
- **Error tracking**: Sentry (or equivalent) across frontend, API, and workers with job_id correlation for traceability.
- **Alerting**: queue depth above threshold, job failure rate spike, BYOK proxy circuit-breaker open state.

### 10.3 Maintainability
- Canonical `PathModel` (Section 7.3) as the enforced boundary between "tracing logic" and "export logic" — new export formats (e.g., future DWG, STEP) plug in without touching tracing code.
- Engine adapters implemented behind a common interface (`TraceEngine.trace(image, settings) -> PathModel`) so Classic/VTracer/BYOK cloud engines are swappable and independently testable.
- Documented DXF layer-naming and version conventions (Section 5.4) versioned alongside the API schema.
- Dependency version pinning for native-code libraries (OpenCV, VTracer, ezdxf) with a documented upgrade/regression-test process, since silent behavior changes in these libraries are a real risk to output consistency.

---

## 11. Risk Assessment and Mitigation Plan

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| DXF output "looks right" visually but fails to import cleanly in real CAD tools (silent corruption) | High (common failure mode of hand-rolled DXF writers) | High | Standardize on ezdxf for all DXF writing; enforce `doc.audit()` in the pipeline itself (not just as a test); maintain cross-tool import test suite (Section 9.1) |
| No dimensional calibration → users unknowingly get geometrically "correct-looking" but scale-wrong exports | High today (feature doesn't yet exist per site review) | High (breaks trust for the core engineering persona) | Ship calibration as a P0 MVP feature; QA report explicitly flags "uncalibrated (pixel-based)" exports |
| Render free/low tier CPU limits cause slow or failed processing under load, especially for VTracer/OpenCV-heavy jobs | Medium–High | Medium | Move worker processing to a right-sized compute tier; decouple workers from the web dyno; add job timeout + graceful failure messaging |
| BYOK API key mishandling (leak via logs, insecure storage) | Low if designed correctly, High impact if it happens | High (trust/legal) | Log scrubbing, in-memory-only key handling by default, encrypted-at-rest only on explicit opt-in, security test in CI (Section 9.1) |
| Naive polyline-only curve export produces bloated, low-quality files unsuitable for CNC/laser (no true arcs) | High without explicit work | Medium–High | Arc/circle fitting as a P0 feature (Section 3.3/7.2) |
| Users upload proprietary/sensitive designs to a public "Gallery" by default | Medium | High (privacy/trust) | Opt-in (not opt-out) gallery visibility; clear data retention policy; auto-delete window |
| Centerline vs. outline tracing confusion leads to unusable output for line-art/engraving use cases | Medium | Medium | Explicit trace-mode selector (P0) with preview showing the difference; smart default based on detected input characteristics (e.g., mostly-thin-stroke input suggests centerline) |
| Cost/rate limits on free BYOK-less tiers (Classic/Advanced engines) abused at scale | Medium | Medium | Rate limiting, batch size caps (Section 5.3), abuse monitoring |
| DXF version mismatches break downstream tools (e.g., older CAM software can't read R2018 features) | Medium | Medium | Default to R12 for maximum compatibility; expose explicit version selector; document trade-offs in-UI (per KaijuConverter-style guidance: R12/AC1009 for laser/CNC/legacy compatibility, R2010/AC1024 for richer hatch/spline support) |
| Scope creep toward full CAD-editor functionality (node editing, layers panel) delays MVP | Medium | Medium | Explicit MVP cut (Section 3.7); manual node editing is P1, not P0 |

---

## 12. Glossary of Terms

| Term | Definition |
|---|---|
| **DXF** | Drawing Exchange Format — Autodesk's open, ASCII tagged-data CAD interchange format, introduced 1982; the primary open interchange target for this tool since DWG is a closed binary spec. |
| **DWG** | AutoCAD's native, proprietary binary drawing format. |
| **ACI** | AutoCAD Color Index — a palette of 1–255 numbered colors used in DXF entity color assignment (group code 62). |
| **Group code** | The integer tag preceding each data value in a DXF file, indicating the type/meaning of that value (DXF's core "tagged data" structure). |
| **LWPOLYLINE** | Lightweight polyline entity (DXF R14+), the standard entity for closed/open 2D cut paths. |
| **Vectorization / Auto-trace** | Converting raster pixel data into vector paths (lines, curves, arcs). |
| **Centerline tracing** | Vectorization mode that traces the skeleton/centerline of a stroke (for line art, single-pass engraving), as opposed to outline tracing which traces the boundary of filled regions. |
| **Outline tracing** | Vectorization mode that traces the boundary contour of filled/solid regions (for logos, stencils, silhouettes). |
| **Node reduction / path simplification** | Reducing the number of vector points while staying within a defined maximum deviation (tolerance), commonly via Douglas-Peucker or Visvalingam-Whyatt algorithms. |
| **Tolerance** | The maximum allowed geometric deviation (typically in real-world units like mm) between the simplified vector path and the original traced geometry. |
| **Calibration** | The process of establishing a pixel-to-real-world-unit scale factor by referencing a known dimension in the source image. |
| **BYOK** | Bring Your Own Key — a model where the user supplies their own third-party API credentials (e.g., for Vectorizer.AI) rather than the platform paying for/managing that usage. |
| **QA report / DXF audit** | A structured validation output (entity counts, open/closed path status, self-intersections, bounding box, unit correctness) confirming the exported file's integrity, e.g., via `ezdxf.audit()`. |
| **Self-intersection** | A path that crosses itself, which can cause undefined behavior in CAM/laser software expecting simple (non-self-intersecting) closed polygons. |
| **Hatch** | A DXF entity type representing a filled pattern/area, used here for "engrave fill" regions as opposed to cut outlines. |
| **VTracer** | An open-source, Rust-based raster-to-vector conversion tool supporting color clustering and curve fitting. |
| **Potrace** | A classic open-source bitmap tracing tool producing smooth vector outlines from binary (black/white) images. |
| **ezdxf** | The actively maintained pure-Python library for reading, writing, and auditing DXF files; recommended as the canonical DXF I/O layer for this system. |

---

*End of document.*
