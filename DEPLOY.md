# dxfvec Deployment Guide

## Free Deployment Options

### 1. Render (Recommended)
**Free tier**: 750 hours/month, auto-sleep after inactivity

```bash
# 1. Push to GitHub
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/dxfvec.git
git push -u origin main

# 2. Deploy on Render
# - Go to https://render.com
# - Sign up with GitHub
# - Click "New Web Service"
# - Select your repo
# - Render auto-detects render.yaml
# - Click "Create Web Service"
```

**Result**: `https://dxfvec.onrender.com`

---

### 2. Railway
**Free tier**: $5 credit/month (enough for always-on)

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and deploy
railway login
railway init
railway up
```

**Result**: `https://your-app.up.railway.app`

---

### 3. Fly.io
**Free tier**: 3 shared-cpu-1x VMs, 160GB bandwidth

```bash
# 1. Install flyctl
curl -L https://fly.io/install.sh | sh

# 2. Deploy
fly auth login
fly launch
fly deploy
```

**Result**: `https://your-app.fly.dev`

---

### 4. Vercel (Serverless)
**Free tier**: 100GB bandwidth, serverless functions

```bash
# 1. Install Vercel CLI
npm i -g vercel

# 2. Deploy
vercel
```

**Result**: `https://your-app.vercel.app`

---

### 5. GitHub Pages (Static)
**Free tier**: 1GB storage, 100GB bandwidth

For static deployment only (no backend processing).

---

### 6. Local Network
```bash
# Run on your machine, accessible on local network
python -m dxfvec.web
# Open http://localhost:5000
# Others can access via http://your-ip:5000
```

---

## Docker Deployment

```bash
# Build
docker build -t dxfvec .

# Run
docker run -p 5000:5000 dxfvec

# Or with docker-compose
docker-compose up -d
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 5000 | Server port |
| `FLASK_DEBUG` | 0 | Debug mode (0/1) |
| `PYTHONUNBUFFERED` | 1 | Python output buffering |

---

## Production Checklist

- [x] Health check endpoint (`/health`)
- [x] CORS enabled
- [x] Max upload size (10MB)
- [x] Gunicorn for production
- [x] Environment-based configuration
- [x] No API keys required
- [x] 100% local processing

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface |
| `/health` | GET | Health check |
| `/convert` | POST | Convert image to DXF |
| `/download/<filename>` | GET | Download DXF file |

---

## Cost Summary

| Platform | Free Tier | Always-On | Notes |
|----------|-----------|-----------|-------|
| Render | 750 hrs/mo | No (sleeps) | Auto-deploy from GitHub |
| Railway | $5 credit | Yes | CLI deployment |
| Fly.io | 3 VMs | Yes | Docker-based |
| Vercel | 100GB BW | Serverless | Function-based |
| Local | Unlimited | Yes | Your machine |

**Total Cost: $0**
