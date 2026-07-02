# dxfvec Deployment Guide

## Render (Recommended)

**Target**: `dxfvec.onrender.com` | **Plan**: Starter ($7/mo for always-on)

### Docker-based deployment (auto-detected from `render.yaml`)

1. Push to GitHub:
   ```bash
   git init && git add . && git commit -m "Production ready"
   git remote add origin https://github.com/yourusername/dxfvec.git
   git push -u origin main
   ```

2. Deploy on Render:
   - Go to https://render.com
   - Click **New Web Service** → Select your repo
   - Render auto-detects `render.yaml` (Docker runtime, health check, worker)
   - Click **Create Web Service**

3. Verify:
   - Health check: `https://dxfvec.onrender.com/api/ping`
   - Web UI: `https://dxfvec.onrender.com`

### Render Configuration (`render.yaml`)

| Setting | Value |
|---------|-------|
| Runtime | Docker |
| Plan | Starter (always-on) |
| Health check | `/api/ping` (30s interval) |
| Workers | 1 (OpenCV memory constraint) |
| Timeout | 300s |
| Auto-deploy | `main` branch |

---

## Docker (Local / Self-hosted)

### Quick start
```bash
docker compose up -d
# or
docker build -t dxfvec . && docker run -p 5000:5000 dxfvec
```

### Production options
```bash
# With resource limits
docker compose -f docker-compose.yml up -d

# View logs
docker compose logs -f dxfvec
```

### Image details
- **Multi-stage build**: builder (compilation) + runtime (minimal)
- **Non-root user**: `dxfvec` (security hardening)
- **Health check**: built-in via `HEALTHCHECK` directive
- **Base**: `python:3.11-slim-bookworm`

---

## Other Platforms

| Platform | Free Tier | Always-On | Method |
|----------|-----------|-----------|--------|
| **Render** | 750 hrs/mo | Starter plan | Docker (render.yaml) |
| **Railway** | $5 credit | Yes | CLI: `railway up` |
| **Fly.io** | 3 VMs | Yes | `fly deploy` |
| **Vercel** | 100GB BW | Serverless | vercel.json |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 5000 | Server port |
| `FLASK_DEBUG` | 0 | Debug mode (0/1) |
| `PYTHONUNBUFFERED` | 1 | Python output buffering |
| `MAX_IMAGE_DIM` | 2048 | Max image dimension (px) |
| `DOWNLOAD_TTL` | 3600 | Download file TTL (seconds) |

### BYOK Cloud Providers (optional)
```bash
DXVEC_VECTORIZER_AI_API_ID=your_id
DXVEC_VECTORIZER_AI_API_SECRET=your_secret
DXVEC_DXFAI_API_KEY=your_key
```

---

## Production Checklist

- [x] Docker multi-stage build (minimal image size)
- [x] Non-root container user (`dxfvec`)
- [x] Health check endpoint (`/api/ping`)
- [x] Gunicorn with access/error logging
- [x] Rate limiting (30 req/min per IP)
- [x] MIME type sniffing guard (magic bytes)
- [x] Decompression bomb protection (40 MP limit)
- [x] File size validation (25 MB single / 50 MB batch)
- [x] Security headers (CSP, HSTS, X-Frame-Options)
- [x] CORS enabled
- [x] 100% local processing (no API keys required)
- [x] DXF audit after every write (ezdxf.audit)
- [x] Structured logging throughout pipeline

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface (single + batch) |
| `/health` | GET | Health check |
| `/convert` | POST | Convert image to DXF |
| `/api/batch` | POST | Batch convert ZIP of images |
| `/download/<filename>` | GET | Download DXF ZIP bundle |
| `/view/<filename>` | GET | DXF canvas viewer |
| `/files` | GET | File gallery |
| `/api/engines` | GET | List engines + presets |
| `/api/presets` | GET | List presets |
| `/api/providers` | GET | List cloud providers |
| `/api/dxf/<name>` | GET | DXF entities as JSON |
| `/api/ping` | GET | Health check |

---

## Cost Summary

| Platform | Free Tier | Always-On | Notes |
|----------|-----------|-----------|-------|
| Render | 750 hrs/mo | Starter $7/mo | Auto-deploy from GitHub |
| Railway | $5 credit | Yes | CLI deployment |
| Fly.io | 3 VMs | Yes | Docker-based |
| Local | Unlimited | Yes | Your machine |

**Total Cost: $0–$7/month**
