# DXFvec BYOK Image Vectorization & DXF Conversion – Full Spec

## 1. Overview

DXFvec is a web and CLI tool for converting raster images (PNG/JPG/WEBP) into CAD/CNC‑ready DXF vectors, with optional AI‑powered engines and a bring‑your‑own‑key (BYOK) model for cloud providers. It competes with tools like VectoSolve, Tracepen Online, Vectorizer.AI, DXFai, generic converters (Convertio, CloudConvert, Coolutils, RapidResizer) and desktop software like Scan2CAD.[^1][^2][^3][^4][^5][^6][^7][^8][^9][^10]

The default experience relies on local algorithms or open‑source AI (no keys required), while advanced cloud AI providers can be plugged in via user‑supplied API keys (BYOK).[^11][^12]

## 2. Market & Competitive Landscape

### 2.1 Online converters and AI DXF tools

- **VectoSolve**: AI image→DXF for CNC and lasers; supports PNG/JPG with CUT/ENGRAVE layers and multi‑format zips; uses a credit‑based pricing model with packs (e.g. 100 conversions) and promises 2–5 second conversion time.[^9][^1]
- **Tracepen Online**: Browser‑based vectorizer that converts PNG/JPG/WEBP to SVG, DXF Lines/Hatch/Faces, PDF; free for basic two‑colour vectorization and requires an account for advanced features.[^13][^2]
- **Vectorizer.AI**: AI‑powered image→vector and JPG→DXF conversion with free previews and paid downloads; supports common raster formats and targets CAD/CNC workflows.[^14][^15][^3][^16]
- **DXFai**: AI‑powered image→DXF and prompt‑to‑design tool for laser cutting and CNC machining; emphasizes outline generation and engraving designs.[^10]
- **Hyper3D image‑to‑DXF**: Browser tool to turn logos, scans and sketches into DXF for CAD/CNC fabrication workflows.[^17]
- **Generic converters**: Convertio, CloudConvert, Coolutils and RapidResizer support JPG/PNG→DXF or SVG→DXF conversion but with limited CNC‑specific controls and generic UX.[^4][^5][^6][^7]
- **ImageToSTL JPG→DXF**: Focused on converting 2D JPG logos/images to DXF model files for AutoCAD and similar CAD applications.[^18]

### 2.2 Desktop professional software

- **Scan2CAD**: Professional raster‑to‑vector conversion software; offers batch JPG→DXF conversion, advanced raster cleaning (despeckle, hole filling), object recognition and accurate scaling for technical drawings and maps.[^19][^8]

### 2.3 Open‑source vectorization engines

- **VTracer (visioncortex/vtracer)**: Open‑source raster→vector converter that turns images into SVG using efficient algorithms; supports coloured graphics and offers presets (bw/poster/photo) and parameters like corner threshold and speckle filtering.[^11]
- Other GitHub projects under `image-vectorization` and `vectorizer` topics provide bitmap→SVG conversion and can inspire AI or advanced algorithms integration.[^20][^21][^22]

## 3. Product Vision & Positioning

DXFvec is positioned as a **free, self‑hostable, CNC/laser‑centric vectorizer** with:

- **Local engines** (Classic and Advanced) requiring no external keys or accounts for core use.[^11]
- **BYOK AI engines** allowing users to integrate commercial AI providers (Vectorizer.AI, DXFai, VectoSolve, etc.) via their own API keys, clearly marked as optional.[^3][^12][^1][^10]
- **DXF modes and layers** focused on cutters/engravers: Lines, Hatch, Faces, CUT/ENGRAVE layers and multi‑format bundles similar to Tracepen and VectoSolve.[^2][^1]

The goal is to combine the DXF export richness and UX simplicity of Tracepen, the AI quality of VectoSolve/Vectorizer.AI, and some of Scan2CAD’s power, without forcing sign‑up or subscriptions for basic use.[^8][^1][^2]

## 4. User Personas & Use Cases

### 4.1 Personas

- **Maker / small CNC shop**: Uses LightBurn, RDWorks, LaserGRBL or similar; needs logo and stencil conversions for laser cutting and engraving with reliable CUT/ENGRAVE layers.[^1][^2]
- **Designer / marketer**: Frequently converts logos, icons and artwork into DXF/SVG for engraving, signage or merch; wants fast, predictable output with minimal CAD knowledge.[^6][^1]
- **Engineer / architect**: Occasionally converts scanned technical drawings, maps or contour plots to DXF for CAD editing; needs scaling, noise control and topology correctness.[^19][^8]

### 4.2 Core use cases

- Convert high‑contrast logos, line art and silhouettes from PNG/JPG/WEBP into clean DXF paths suitable for laser cutting and CNC routing.[^2][^3][^1]
- Convert scanned plans, maps and technical drawings into DXF with adjustable noise removal, thresholding and scaling, similar to Scan2CAD workflows.[^8][^19]
- Export multi‑format bundles (DXF, SVG, PNG preview) to support hybrid design + CAD workflows.[^1][^2]

## 5. Detailed Product Requirements (PRD)

### 5.1 Functional scope

#### 5.1.1 Inputs and validation

- Supported raster formats: PNG, JPG/JPEG, WEBP initially (optionally BMP/GIF later), aligning with major online tools.[^16][^14][^3][^2][^1]
- File size limit configurable per deployment (default 20–25 MB) with clear error messages and UI hints.[^1]
- Validation for corrupted or unsupported images with user‑friendly feedback.

#### 5.1.2 DXF output modes

- **DXF Lines**: Polylines representing outlines and paths for cutting routers and lasers.[^2]
- **DXF Hatch**: Hatch entities representing filled/engrave regions for engraving passes.[^2]
- **DXF Faces**: Closed polylines or 2D faces for 3D modelling tools like SketchUp and Blender.[^2]
- DXF flavour compatible with AutoCAD 2000 and common CAM software, similar to professional converters.[^8][^1]

#### 5.1.3 Layer semantics and colouring

- Automatic layer assignment:
  - **CUT** layer (e.g. colour 1/red) for outer outlines and cut paths.[^1]
  - **ENGRAVE** layer (e.g. colour 5/blue) for filled regions or hatch areas.
- Legend in UI explaining layer names and colours, mirroring CNC/laser usage.

#### 5.1.4 Engines and BYOK model

- **Engine types**:
  - **Classic engine**: deterministic pipeline using image processing and contour tracing; always available, no API keys required.
  - **Advanced engine**: local AI‑style engine using open‑source vectorizers like VTracer; no external keys required.[^11]
  - **Cloud AI engines (BYOK)**: optional providers that require user‑supplied API keys, such as Vectorizer.AI, DXFai or similar image→vector APIs.[^12][^3][^10][^1]

- **Configuration and UX**:
  - Web UI: dropdown or segmented control `Engine: Classic / Advanced (local AI) / Cloud AI (BYOK)`.
  - CLI: flag `--engine classic|advanced|cloud:<provider>`.
  - Cloud AI providers are disabled by default and surfaced only when API keys are configured by the operator or user.

#### 5.1.5 Controls and presets

- Basic controls (visible for all engines):
  - Threshold slider.
  - Smoothing slider (curve simplification level).
  - Corner sensitivity (sharp vs smooth corners).
  - Noise filtering level (“remove speckles/holes”), inspired by Scan2CAD’s raster cleaning controls.[^8]

- Advanced controls (visible in an “Expert” section):
  - Minimum region size for vectorization.
  - Maximum path length or node count.
  - Scaling target dimensions (width or height in mm/inches) and output units, matching CAD expectations.[^8]

- Presets:
  - “Logo engraving”.
  - “Laser stencil”.
  - “Technical drawing”.
  - “Contour map”.

Each preset adjusts preprocessing and vectorization parameters to suit typical jobs described for tools like Scan2CAD, VectoSolve and similar converters.[^1][^8]

#### 5.1.6 Preview and interactive UX

- Side‑by‑side preview of original raster and vector output with:
  - Zoom and pan.
  - Toggle between raster, pure vector, and overlay modes.
  - Optional display of nodes and paths.

- Legend indicating layer colours and DXF modes (Lines/Hatch/Faces).

#### 5.1.7 Outputs and downloads

- Per‑mode downloads: DXF, SVG, PNG preview.
- ZIP bundle download including all selected formats, similar to VectoSolve’s multi‑format packs.[^1]
- For Cloud AI engines, surface information about provider (name, cost model, limitations) in a tooltip or info section without leaking keys.

### 5.2 Non‑functional requirements

- **Performance**: Typical logo‑size images should convert in <3–5 seconds on standard cloud hosting, comparable to AI‑based online converters.[^9][^1]
- **Reliability**: High success rate for valid inputs; robust error handling and clear feedback on failure.
- **Compatibility**: DXF outputs tested manually in LightBurn, AutoCAD, Fusion 360, VCarve, Inkscape, RDWorks, LaserGRBL, SketchUp and Blender.[^2][^8][^1]
- **Security and privacy**: Public instances should not persist user images after conversion; BYOK secrets stored securely (environment variables or encrypted config).
- **Accessibility**: Keyboard‑friendly controls, high‑contrast UI, responsive layout for desktops and tablets.

### 5.3 Success metrics

- Average conversion time and resource usage by engine.
- Percentage of DXF files that open without warnings in target software (QA metric).
- User feedback scores on “ready‑to‑cut” quality and ease of use.
- Adoption rate of Advanced and Cloud AI engines vs Classic engine.

## 6. Technical Requirements & Design (TRD)

### 6.1 Architecture

DXFvec uses a modular architecture with distinct responsibilities for preprocessing, vectorization, DXF writing, pipeline orchestration, providers, CLI and web frontends.

- **Frontend surfaces**:
  - Web application served by `web.py` (FastAPI/Flask/Streamlit or similar).
  - CLI executable powered by `cli.py` with subcommands for single and batch conversion.

- **Backend pipeline**:
  - Core Python modules `preprocess.py`, `vectorizer.py`, `dxf_writer.py` and `pipeline.py` for deterministic and AI‑style vectorization flows.

- **Providers layer (BYOK)**:
  - `providers.py` defines interfaces for Classic, Advanced (local AI) and Cloud AI engines, with configuration for keys and options.

### 6.2 Module designs

- `preprocess.py`:
  - Input validation and format checks.
  - Conversion to grayscale or colour spaces as required.
  - Thresholding (global, adaptive) and noise removal (speckle filtering, hole filling) similar to raster cleaning operations in professional converters.[^8]

- `vectorizer.py`:
  - Contour extraction and path generation using image processing algorithms.
  - Smoothing and corner handling with configurable thresholds.
  - Labeling of paths as outline versus fill regions.

- `dxf_writer.py`:
  - Mapping of vector paths to DXF Lines/Hatch/Faces entities.[^2]
  - Layer assignment for CUT/ENGRAVE semantics, colour codes, line types.[^1]
  - Ensuring AutoCAD‑compatible DXF structure and testing across major CAD/CAM tools.[^8]

- `pipeline.py`:
  - High‑level API `convert_image_to_dxf(image_bytes, config)` that plugs in a selected provider and returns DXF/SVG/PNG outputs.

- `providers.py` (BYOK engine hub):
  - **ClassicProvider**: wraps deterministic pipeline (preprocess + vectorizer + dxf_writer).
  - **VTracerProvider**: integrates VTracer to convert images to SVG, then passes paths to `dxf_writer` for DXF export.[^11]
  - **CloudAIProvider** implementations:
    - `VectorizerAIProvider`: uses Vectorizer.AI’s API via Python SDK to obtain SVG/DXF, controlled by user API key.[^3][^12]
    - `DXFaiProvider`: calls DXFai’s image→DXF API when keys are configured.[^10]
    - Additional providers for VectoSolve or Hyper3D if their APIs are accessible.[^17][^1]

Each Cloud provider reads keys from environment variables or configuration files and is disabled when keys are absent, aligning with BYOK.[^12]

- `web.py`:
  - HTTP endpoints: `/upload`, `/convert`, `/download/<id>`.
  - Engine selection and presets passed to backend via JSON payload.

- `cli.py`:
  - Commands like `dxfvec convert input.png --engine classic --mode lines --out output.dxf`.
  - Batch mode: `dxfvec batch ./input_dir --engine advanced --mode lines,hatch --out ./out_dir`.

### 6.3 Data flow with BYOK engines

1. Web or CLI receives image and configuration (engine, mode, controls).
2. `pipeline.py` selects provider based on engine and availability (Classic/Advanced/Cloud). If Cloud provider lacks a key, it falls back to Classic or Advanced.
3. Provider runs preprocessing and vectorization (local algorithms or remote AI), yielding vector paths and metadata.
4. `dxf_writer.py` converts paths and metadata into DXF entities with appropriate layers and modes.
5. Output bundle (DXF/SVG/PNG/ZIP) is returned to frontend and offered for download.

### 6.4 Performance and scaling

- Deterministic engines optimized to avoid unnecessary copies and re‑allocations.
- Cloud AI providers integrated with timeouts and circuit breakers; fallback to local engines on failure.
- Horizontal scaling via containerization (Dockerfile and docker‑compose) and cloud configs (render.yaml, vercel.json, Procfile) already present in the repo.

### 6.5 Security and BYOK handling

- API keys managed via environment variables, secrets managers or encrypted configuration files; never logged.
- Web UI should never expose keys; toggles merely indicate provider availability.
- Public demo deployments should use only Classic/Advanced engines to avoid sharing private credentials.

### 6.6 Testing and QA

- Unit tests for preprocessing, vectorization, DXF writing, and provider selection logic.
- Golden‑file tests: given canonical test images, verify the structure and topology of outputs across engines.
- Manual QA in CAD/CAM software to ensure DXF compatibility and layer semantics.

## 7. AI Integration Design (Local & BYOK)

### 7.1 Local AI via VTracer

- Integrate VTracer using Python bindings to obtain high‑quality SVG paths from raster images.[^11]
- Use VTracer presets and parameters (corner threshold, speckle filtering) to implement Advanced engine settings and presets.
- Convert SVG paths to DXF entities via `dxf_writer`, preserving colour or layer information for CUT/ENGRAVE semantics.

### 7.2 Local ML (segmentation‑based)

- Optional integration of lightweight segmentation models (e.g. U‑Net variants) to produce masks for outlines and engrave regions, followed by contour tracing.
- This approach mirrors AI DXF tools that emphasize outline generation and engrave design extraction.[^17][^10]

### 7.3 BYOK Cloud AI providers

- CloudAIProviders interface wraps external APIs like Vectorizer.AI, DXFai or similar image→vector services.[^3][^10]
- Each provider exposes configuration for endpoint, key, timeouts and output formats.
- Engine selection logic routes to these providers only when a valid key is configured and the user chooses Cloud AI.

## 8. Documentation & User Guidance

### 8.1 User documentation

- Explain supported input formats and best practices (high‑contrast logos, cleaned scans, adequate resolution), similar to tips found on VectoSolve and Vectorizer.AI.[^3][^1]
- Document DXF modes and layer semantics for common CNC/laser workflows.[^2][^1]
- Provide guidance on choosing engines: Classic vs Advanced vs Cloud AI, including trade‑offs of speed, quality and privacy.

### 8.2 Operator documentation

- Explain how to configure BYOK providers, including environment variables and secret management.[^12]
- Describe resource requirements and scaling strategies for local AI/ML engines.

## 9. Summary

This report specifies DXFvec as a multi‑engine, CNC‑centric image→DXF tool with a default local pipeline and optional BYOK AI integration. It draws on patterns from leading tools such as VectoSolve, Tracepen Online, Vectorizer.AI, DXFai, Hyper3D, generic file converters and Scan2CAD for feature and UX design. DXFvec’s differentiator is the combination of self‑hostability, key‑free baseline functionality, explicit BYOK AI support, CNC‑aware DXF layering and a unified web/CLI pipeline.[^13][^10][^17][^3][^11][^8][^1][^2]

---

## References

1. [Image to DXF Converter — CNC & Laser-Ready Files ...](https://vectosolve.com/convert/image-to-dxf) - Turn any PNG or JPG into a clean DXF for CNC, laser, or plasma. AI traces precise cut paths with CUT...

2. [Tracepen Online: Free Image Vectorizer — SVG, DXF, PDF & CNC](https://3dshouse.com/tracepen-online/) - Tracepen Online converts PNG, JPG, or WebP to SVG, DXF, and PDF right in your browser — free for 2-c...

3. [JPG to DXF Converter | Image to DXF for AutoCAD & CNC - Vectorizer.AI](https://vectorizer.ai/jpg-to-dxf-converter) - Convert JPG images into DXF vectors for CAD and CNC workflows. AI tracing, free preview, editable ou...

4. [Convert PNG to DXF Online — Free Image to CAD Converter](https://www.coolutils.com/online/PNG-to-DXF) - Convert PNG images to DXF format for AutoCAD, CNC routers, and laser cutters online. Free, no regist...

5. [Free Online Raster to Vector Converter](https://online.rapidresizer.com/tracer.php) - Automatically convert a picture to a PDF, SVG, DXF, AI, or EPS vector drawing. Trace outer- or cente...

6. [JPG to DXF — CAD Converter](https://convertio.co/jpg-dxf/) - Convert JPG to DXF for free on convertio.co. Transform raster images into AutoCAD-compatible DXF dra...

7. [SVG to DXF Converter](https://cloudconvert.com/svg-to-dxf) - SVG to DXF Converter - CloudConvert is a free & fast online file conversion service.

8. [Convert JPG to DXF | Professional Conversion Software](https://www.scan2cad.com/convert-jpg-dxf/) - Convert JPG to DXF with Scan2CAD. Professional-grade CAD conversion software. Try for free. Download...

9. [Image to DXF Converter Free Online 2026 - VectoSolve](https://vectosolve.com/el/convert/image-to-dxf) - Convert PNG or JPG to DXF for CNC machines and laser cutters in 2-5 seconds. AI creates precise vect...

10. [Image to DXF Converter](https://dxfai.ai/) - Convert any image to DXF vector files for laser cutting and CNC machining. AI-powered outline genera...

11. [visioncortex/vtracer: Raster to Vector Graphics Converter - GitHub](https://github.com/visioncortex/vtracer) - visioncortex VTracer is an open source software to convert raster images (like jpg & png) into vecto...

12. [Python SDK for Vectorizer.AI - GitHub](https://github.com/mitchbregs/vectorizer-ai) - Python SDK for Vectorizer.AI. Contribute to mitchbregs/vectorizer-ai development by creating an acco...

13. [Tracepen Online — Chuyển Ảnh Sang SVG, DXF Miễn Phí](https://3dshouse.com/vi/tracepen-online/) - Tracepen Online – chuyển ảnh raster sang vector sạch ngay trên trình duyệt. Xuất SVG, PNG, PDF, DXF ...

14. [Images से DXF ऑनलाइन कन्वर्ट करें](https://hi.vectorizer.ai/image-to-dxf-converter) - इमेजिस को CAD, CNC, लेज़र कटिंग और टेक्निकल ड्राइंग के लिए संपादन करने योग्य DXF वेक्टर में बदलें। A...

15. [Konwerter obrazu na DXF | Konwertuj obrazy na DXF dla CAD i CNC](https://pl.vectorizer.ai/image-to-dxf-converter) - Konwertuj obrazy na edytowalne wektory DXF dla CAD, CNC, cięcia laserowego i rysowania technicznego....

16. [Converti Immagini in DFX per CAD e CNC - Vectorizer.AI](https://it.vectorizer.ai/image-to-dxf-converter) - Converti immagini in vettori modificabili DFX per CAD, CNC, taglio laser, e disegno tecnico. Support...

17. [Image to DXF Converter - Convert Photos to DXF](https://hyper3d.ai/tools/image-to-dxf) - Convert images to DXF with Hyper3D. Turn logos, scans, and sketches into CAD-ready output for CNC, l...

18. [Convert JPG to AutoCAD DXF Format for Free](https://imagetostl.com/convert/file/jpg/to/dxf) - Convert JPG to DXF AutoCAD with our free and fast online tool. Convert your 2D JPG image or logo int...

19. [Scan2CAD Regular](https://cadvance.com/scan2cad.htm)

20. [GitHub - delbeke/vectorizer: Convert bitmap to SVG vector image](https://github.com/delbeke/vectorizer) - Convert bitmap to SVG vector image. Contribute to delbeke/vectorizer development by creating an acco...

21. [Build software better, together](https://github.com/topics/image-vectorization) - GitHub is where people build software. More than 150 million people use GitHub to discover, fork, an...

22. [vectorizer · GitHub Topics](https://github.com/topics/vectorizer) - A java based vectorization software which takes a raster image as input and convert it to a vector f...

