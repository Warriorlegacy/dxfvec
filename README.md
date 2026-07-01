# DXFvec

**100% free image vectorization and DXF conversion** — no API keys required.  
Convert raster images (PNG, JPG, WEBP, BMP, TIFF) into CAD/CNC-ready DXF vectors with CUT/ENGRAVE/BEND/DIM layer semantics.

## Features

- **3 engines**: Classic (OpenCV, fast), Advanced (VTracer AI, high-quality), Cloud AI (BYOK)
- **3 DXF modes**: Lines (cut paths), Hatch (engrave fills), Faces (closed shapes)
- **4 presets**: Logo Engrave, Laser Stencil, Technical Drawing, Contour Map
- **CNC layers**: Auto-assigns CUT (red), ENGRAVE (blue), BEND (blue dashed), DIM (green)
- **Web UI**: Drag-and-drop, engine selector, real-time preview, canvas viewer with pan/zoom
- **CLI**: `dxfvec convert`, `modify`, `enhance`, `engines`, `presets`, `providers`
- **BYOK cloud**: Vectorizer.AI and DXFai via your own API keys
- **Multi-format**: DXF + SVG + PNG preview in ZIP bundle
- **Viewer**: Pan/zoom, Print, PDF, raster/vector/overlay toggle, nodes display

## Quick Start

```bash
pip install -r requirements.txt
pip install -e .
dxfvec convert input.png --engine classic --mode lines -o output.dxf
```

### Web Server

```bash
python -m dxfvec.web
# Open http://localhost:5000
```

### Production (Render)

```bash
gunicorn --bind 0.0.0.0:5000 --workers 1 dxfvec.web:app
```

## CLI Usage

```bash
dxfvec convert image.png [--engine classic|advanced|cloud:provider] [--mode lines|hatch|faces] [--preset logo_engrave|laser_stencil|technical_drawing|contour_map] [--scale 2.5] [--output-dir ./out]
dxfvec modify image.png [--rotate 90] [--resize 800x600] [--enhance] [--denoise] [--sharpen] [--deskew]
dxfvec engines
dxfvec presets
dxfvec providers
```

## API Endpoints

| Route | Method | Description |
|---|---|---|
| `/` | GET | Upload form |
| `/convert` | POST | Convert image (multipart form) |
| `/download/<filename>` | GET | Download ZIP bundle (DXF + SVG + PNG) |
| `/view/<filename>` | GET | DXF canvas viewer |
| `/files` | GET | File gallery |
| `/api/engines` | GET | List engines + presets |
| `/api/presets` | GET | List presets |
| `/api/providers` | GET | List cloud providers |
| `/api/dxf/<name>` | GET | DXF entities as JSON |
| `/api/svg/<filename>` | GET | Download SVG from bundle |
| `/api/pdf` | POST | Generate PDF from canvas data |
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
- **Vercel**: vercel.json + Procfile included
