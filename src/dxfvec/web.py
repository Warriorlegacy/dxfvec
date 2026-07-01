"""Web interface for dxfvec — free image vectorization.

Usage:
  python -m dxfvec.web
  # Then open http://localhost:5000
  
Production:
  gunicorn --bind 0.0.0.0:5000 --workers 1 dxfvec.web:app
"""
from __future__ import annotations

import json
import math
import tempfile
import time
import zipfile
from pathlib import Path

import cv2
import ezdxf
from flask import Flask, render_template_string, request, send_file, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Max upload size: 10MB
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "dxfvec_downloads"
MAX_IMAGE_DIM = 2048
DOWNLOAD_TTL_SECONDS = 3600


def _cleanup_old_downloads():
    try:
        if DOWNLOAD_DIR.exists():
            now = time.time()
            for f in DOWNLOAD_DIR.iterdir():
                if f.is_file() and (now - f.stat().st_mtime) > DOWNLOAD_TTL_SECONDS:
                    f.unlink(missing_ok=True)
    except Exception:
        pass

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>dxfvec — Image Vectorization</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               background: #0f1117; color: #e1e4e8; padding: 2rem; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #58a6ff; margin-bottom: 0.5rem; }
        .subtitle { color: #8b949e; margin-bottom: 2rem; }
        .badge { display: inline-block; background: #238636; color: white; padding: 2px 8px; 
                 border-radius: 12px; font-size: 0.75rem; margin-left: 0.5rem; }
        .upload-area { border: 2px dashed #30363d; border-radius: 8px; padding: 3rem; 
                       text-align: center; cursor: pointer; transition: border-color 0.2s; }
        .upload-area:hover { border-color: #58a6ff; }
        .upload-area.dragover { border-color: #58a6ff; background: rgba(88,166,255,0.1); }
        .upload-icon { font-size: 3rem; margin-bottom: 1rem; }
        .form-group { margin: 1.5rem 0; }
        label { display: block; color: #8b949e; margin-bottom: 0.5rem; font-size: 0.9rem; }
        input[type="text"], select { width: 100%; padding: 0.75rem; background: #161b22; 
               border: 1px solid #30363d; border-radius: 6px; color: #e1e4e8; font-size: 1rem; }
        input:focus, select:focus { outline: none; border-color: #58a6ff; }
        .btn { background: #238636; color: white; border: none; padding: 0.75rem 1.5rem; 
               border-radius: 6px; cursor: pointer; font-size: 1rem; width: 100%; }
        .btn:hover { background: #2ea043; }
        .btn:disabled { background: #21262d; color: #484f58; cursor: not-allowed; }
        .result { margin-top: 2rem; padding: 1.5rem; background: #161b22; border-radius: 8px; 
                  border: 1px solid #30363d; }
        .result h3 { color: #58a6ff; margin-bottom: 1rem; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 1rem 0; }
        .stat { text-align: center; }
        .stat-value { font-size: 1.5rem; font-weight: bold; color: #58a6ff; }
        .stat-label { font-size: 0.8rem; color: #8b949e; }
        .download-btn { display: inline-block; background: #1f6feb; color: white; padding: 0.5rem 1rem; 
                        border-radius: 6px; text-decoration: none; margin-top: 1rem; }
        .download-btn:hover { background: #388bfd; }
        .error { color: #f85149; margin-top: 1rem; }
        .features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin: 2rem 0; }
        .feature { background: #161b22; padding: 1rem; border-radius: 8px; border: 1px solid #30363d; }
        .feature h4 { color: #58a6ff; margin-bottom: 0.5rem; }
        .feature p { color: #8b949e; font-size: 0.85rem; }
        #preview { max-width: 100%; max-height: 300px; margin-top: 1rem; border-radius: 8px; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <nav style="display:flex; gap:1rem; align-items:center; margin-bottom:1rem;">
            <h1 style="margin:0;">dxfvec <span class="badge">100% FREE</span></h1>
            <a href="/files" style="color:#8b949e; text-decoration:none; font-size:0.9rem; margin-left:auto;">📂 Gallery</a>
        </nav>
        <p class="subtitle">Image Vectorization & DXF Conversion — No API Keys Required</p>
        
        <div class="features">
            <div class="feature">
                <h4>🔧 Image Modify</h4>
                <p>Rotate, resize, enhance, denoise, sharpen, deskew</p>
            </div>
            <div class="feature">
                <h4>📐 Vectorize</h4>
                <p>Auto-detect outlines, holes, lines, polygons</p>
            </div>
            <div class="feature">
                <h4>📄 DXF Export</h4>
                <p>CAD-ready with CUT/BEND/DIM layers</p>
            </div>
        </div>
        
        <form id="upload-form" enctype="multipart/form-data">
            <div class="upload-area" id="drop-zone">
                <div class="upload-icon">📁</div>
                <p>Drag & drop image here or click to browse</p>
                <p style="color: #8b949e; font-size: 0.85rem; margin-top: 0.5rem;">PNG, JPG, BMP, TIFF</p>
                <input type="file" id="file-input" name="image" accept="image/*" style="display: none;">
            </div>
            
            <img id="preview" class="hidden" alt="Preview">
            
            <div class="form-group">
                <label for="scale">Scale (optional)</label>
                <input type="text" id="scale" name="scale" placeholder="e.g. 64px=20mm or 3.2">
            </div>
            
            <div class="form-group">
                <label for="min-area">Min contour area</label>
                <input type="text" id="min-area" name="min-area" value="100" placeholder="100">
            </div>
            
            <button type="submit" class="btn" id="submit-btn" disabled>Convert to DXF</button>
        </form>
        
        <div id="result" class="result hidden"></div>
        <div id="error" class="error hidden"></div>
    </div>
    
    <script>
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const preview = document.getElementById('preview');
        const submitBtn = document.getElementById('submit-btn');
        const form = document.getElementById('upload-form');
        const resultDiv = document.getElementById('result');
        const errorDiv = document.getElementById('error');
        
        dropZone.addEventListener('click', () => fileInput.click());
        
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                handleFile(e.dataTransfer.files[0]);
            }
        });
        
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) handleFile(e.target.files[0]);
        });
        
        function handleFile(file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                preview.src = e.target.result;
                preview.classList.remove('hidden');
                submitBtn.disabled = false;
            };
            reader.readAsDataURL(file);
        }
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            submitBtn.disabled = true;
            submitBtn.textContent = 'Converting...';
            resultDiv.classList.add('hidden');
            errorDiv.classList.add('hidden');
            
            const formData = new FormData(form);
            
            try {
                const response = await fetch('/convert', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Conversion failed');
                }
                
                const data = await response.json();
                
                resultDiv.innerHTML = `
                    <h3>Conversion Complete</h3>
                    <div class="stats">
                        <div class="stat">
                            <div class="stat-value">${data.stats.outlines}</div>
                            <div class="stat-label">Outlines</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">${data.stats.holes}</div>
                            <div class="stat-label">Holes</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">${data.stats.lines}</div>
                            <div class="stat-label">Lines</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">${data.stats.polygons}</div>
                            <div class="stat-label">Polygons</div>
                        </div>
                    </div>
                    <div style="display:flex; gap:0.75rem; margin-top:1rem;">
                        <a href="/view/${data.filename}" class="download-btn" style="background:#1f6feb;">🔍 View DXF</a>
                        <a href="/download/${data.filename}" class="download-btn">⬇ Download DXF</a>
                    </div>
                `;
                resultDiv.classList.remove('hidden');
            } catch (err) {
                errorDiv.textContent = err.message;
                errorDiv.classList.remove('hidden');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Convert to DXF';
            }
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/health")
def health():
    """Health check endpoint for deployment platforms."""
    return jsonify({"status": "ok", "service": "dxfvec", "version": "1.0.0"})

@app.route("/convert", methods=["POST"])
def convert():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    _cleanup_old_downloads()

    DOWNLOAD_DIR.mkdir(exist_ok=True)

    scale = request.form.get("scale", "").strip() or None
    min_area = int(request.form.get("min-area", 100))

    try:
        import cv2
        import numpy as np
    except ImportError:
        return jsonify({"error": "Server misconfigured: OpenCV not available"}), 500

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / file.filename
        file.save(str(input_path))

        img = cv2.imread(str(input_path))
        if img is None:
            return jsonify({"error": "Cannot load image — unsupported format"}), 400

        h, w = img.shape[:2]
        max_dim = max(h, w)
        if max_dim > MAX_IMAGE_DIM:
            scale_px = MAX_IMAGE_DIM / max_dim
            new_w, new_h = int(w * scale_px), int(h * scale_px)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            resized_path = Path(tmpdir) / f"resized_{file.filename}"
            cv2.imwrite(str(resized_path), img)
            input_path = resized_path

        scale_factor = None
        if scale:
            import re
            if re.fullmatch(r"\d+(\.\d+)?", scale):
                scale_factor = float(scale)
            else:
                m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*px\s*=\s*(\d+(?:\.\d+)?)\s*(mm|cm|in)", scale)
                if m:
                    px = float(m.group(1))
                    real = float(m.group(2))
                    unit = m.group(3)
                    if unit == "in":
                        real *= 25.4
                    elif unit == "cm":
                        real *= 10
                    scale_factor = px / real

        from .vectorizer import vectorize_image
        output_dir = Path(tmpdir) / "output"

        try:
            result = vectorize_image(
                input_path, output_dir,
                scale_factor=scale_factor,
                min_area=min_area
            )
        except Exception as e:
            return jsonify({"error": f"Vectorization error: {e}"}), 500

        dxf_path = Path(result["dxf"])
        if not dxf_path.exists():
            return jsonify({"error": "DXF generation failed"}), 500

        zip_path = Path(tmpdir) / "result.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(dxf_path, dxf_path.name)
            review_src = Path(result["review"])
            if review_src.exists():
                zf.write(review_src, "review.md")

        final_zip = DOWNLOAD_DIR / f"{input_path.stem}.zip"
        final_zip.write_bytes(zip_path.read_bytes())

    return jsonify({
        "filename": final_zip.name,
        "stats": result["stats"]
    })

@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/download/<filename>")
def download(filename):
    file_path = DOWNLOAD_DIR / filename
    if not file_path.exists():
        return jsonify({"error": "File not found — it may have expired. Please reconvert."}), 404
    return send_file(file_path, as_attachment=True, download_name=filename)


# ── DXF Viewer API ─────────────────────────────────────────────────────────

@app.route("/api/ping")
def ping():
    return jsonify({"status": "ok"})

@app.route("/api/files")
def list_files():
    """Return list of available DXF zip files with metadata."""
    _cleanup_old_downloads()
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    files = []
    for f in sorted(DOWNLOAD_DIR.glob("*.zip"), reverse=True):
        try:
            stat = f.stat()
            files.append({
                "filename": f.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
        except OSError:
            pass
    return jsonify({"files": files})


def _dxf_to_json(dxf_path: Path) -> dict:
    """Convert DXF entities to JSON for the canvas renderer."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    layers = {}
    entities = []

    for ent in msp:
        layer = ent.dxf.get("layer", "0")
        layers.setdefault(layer, len(layers))
        e = {"layer": layer, "color": _aci_color(ent)}

        if ent.dxftype() == "LINE":
            e.update({"type": "line",
                       "x1": ent.dxf.start.x, "y1": ent.dxf.start.y,
                       "x2": ent.dxf.end.x,   "y2": ent.dxf.end.y})
        elif ent.dxftype() == "LWPOLYLINE":
            pts = [{"x": p[0], "y": p[1]} for p in ent.get_points()]
            e.update({"type": "polyline", "closed": ent.closed, "points": pts})
        elif ent.dxftype() == "POLYLINE":
            pts = []
            try:
                for v in ent.vertices:
                    loc = v.dxf.location
                    pts.append({"x": loc.x, "y": loc.y})
            except Exception:
                pass
            e.update({"type": "polyline", "closed": getattr(ent, "closed", False), "points": pts})
        elif ent.dxftype() == "CIRCLE":
            e.update({"type": "circle",
                       "cx": ent.dxf.center.x, "cy": ent.dxf.center.y,
                       "r": float(ent.dxf.radius)})
        elif ent.dxftype() == "ELLIPSE":
            e.update({"type": "ellipse",
                       "cx": ent.dxf.center.x, "cy": ent.dxf.center.y,
                       "a": float(ent.dxf.major_axis.magnitude),
                       "b": float(ent.dxf.major_axis.magnitude * ent.dxf.ratio),
                       "angle": float(ent.dxf.rotation * 180 / math.pi)})
        elif ent.dxftype() == "POINT":
            e.update({"type": "point",
                       "x": ent.dxf.location.x, "y": ent.dxf.location.y})
        elif ent.dxftype() in ("TEXT", "MTEXT"):
            e.update({"type": "text",
                       "x": ent.dxf.insert.x, "y": ent.dxf.insert.y,
                       "text": ent.text if ent.dxftype() == "MTEXT" else ent.dxf.text,
                       "height": float(ent.dxf.height if ent.dxftype() == "TEXT"
                                       else ent.dxf.char_height)})
        else:
            continue
        entities.append(e)

    # Compute bounding box manually from all entity coordinates
    xs: list[float] = []
    ys: list[float] = []
    for ent in msp:
        try:
            for x, y in _entity_xy(ent):
                xs.append(x); ys.append(y)
        except Exception:
            pass
    bbox = None
    if xs:
        bbox = {"minx": min(xs), "miny": min(ys),
                "maxx": max(xs), "maxy": max(ys)}

    return {"entities": entities, "layers": list(layers.keys()),
            "bbox": bbox}


def _entity_xy(ent):
    """Yield (x, y) coordinate samples from a DXF entity."""
    t = ent.dxftype()
    if t == "LINE":
        yield ent.dxf.start.x, ent.dxf.start.y
        yield ent.dxf.end.x,   ent.dxf.end.y
    elif t == "LWPOLYLINE":
        for p in ent.get_points():
            yield p[0], p[1]
    elif t == "POLYLINE":
        for v in ent.vertices:
            try:
                loc = v.dxf.location
                yield loc.x, loc.y
            except Exception:
                pass
    elif t in ("CIRCLE", "ELLIPSE"):
        cx, cy = ent.dxf.center.x, ent.dxf.center.y
        if t == "CIRCLE":
            r = float(ent.dxf.radius)
        else:
            r = float(ent.dxf.major_axis.magnitude)
        for a in [0, math.pi / 2, math.pi, 3 * math.pi / 2]:
            yield cx + r * math.cos(a), cy + r * math.sin(a)
    elif t == "POINT":
        yield ent.dxf.location.x, ent.dxf.location.y
    elif t in ("TEXT", "MTEXT"):
        yield ent.dxf.insert.x, ent.dxf.insert.y
    elif t == "SPLINE":
        for p in ent.control_points:
            yield p.x, p.y
    elif t in ("ARC", "SOLID", "TRACE"):
        try:
            ext = ent.extents()
            b = ext.bbox
            yield b.extmin.x, b.extmin.y
            yield b.extmax.x, b.extmax.y
        except Exception:
            pass


def _aci_color(ent) -> str:
    """Map DXF ACI color index to a CSS colour string."""
    palette = {
        1: "#ff0000", 2: "#ffff00", 3: "#00ff00", 4: "#00ffff",
        5: "#0000ff", 6: "#ff00ff", 7: "#ffffff", 8: "#808080",
        9: "#c0c0c0", 0: "#ffffff",
    }
    try:
        return palette.get(int(ent.dxf.get("color", 7)), "#ffffff")
    except Exception:
        return "#ffffff"


def _mag(v) -> float:
    """Magnitude of a 2D or 3D DXF vector."""
    x, y = v.x, v.y
    try:
        z = v.z
        return math.sqrt(x * x + y * y + z * z)
    except AttributeError:
        return math.sqrt(x * x + y * y)


LWPOLYLINE_CURVE_ERROR = 1e-3


@app.route("/api/dxf/<name>")
def dxf_json(name):
    """Return parsed DXF as JSON. Accepts both .dxf and .zip files."""
    _cleanup_old_downloads()
    zip_path = DOWNLOAD_DIR / name
    if not zip_path.exists():
        # try direct dxf
        dxf_path = DOWNLOAD_DIR / name.replace(".zip", ".dxf")
        if not dxf_path.exists():
            return jsonify({"error": "File not found"}), 404
        zip_path = None

    if zip_path:
        try:
            with zipfile.ZipFile(zip_path) as zf:
                dxf_names = [n for n in zf.namelist() if n.endswith(".dxf")]
                if not dxf_names:
                    return jsonify({"error": "No DXF in archive"}), 400
                import io, os as _os
                tmp = Path(tempfile.mkdtemp())
                zf.extractall(tmp)
                dxf_path = tmp / dxf_names[0]
        except Exception as e:
            return jsonify({"error": f"Zip error: {e}"}), 400

    try:
        data = _dxf_to_json(dxf_path)
        data["filename"] = name
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"DXF parse error: {e}"}), 400

@app.route("/files")
def files_page():
    return render_template_string(FILES_TEMPLATE)

@app.route("/view/<name>")
def view_page(name):
    return render_template_string(VIEWER_TEMPLATE, filename=name)


FILES_TEMPLATE = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>dxfvec — File Gallery</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0f1117; color: #e1e4e8; padding: 2rem; }
        .container { max-width: 900px; margin: 0 auto; }
        h1 { color: #58a6ff; margin-bottom: 0.5rem; }
        .subtitle { color: #8b949e; margin-bottom: 2rem; }
        a { color: #58a6ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .back { display: inline-block; margin-bottom: 1.5rem; color: #8b949e; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #30363d; }
        th { color: #8b949e; font-size: 0.8rem; text-transform: uppercase; }
        tr:hover td { background: #161b22; }
        .empty { color: #484f58; text-align: center; padding: 3rem; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back">← Back to converter</a>
        <h1>📂 DXF File Gallery</h1>
        <p class="subtitle">Click a file to view it in the DXF viewer</p>
        <table id="files-table">
            <thead><tr><th>File</th><th>Size</th><th>Modified</th><th>Action</th></tr></thead>
            <tbody></tbody>
        </table>
        <div id="empty" class="empty hidden">No converted files yet. Upload an image first!</div>
    </div>
    <script>
        async function load() {
            const res = await fetch('/api/files');
            const data = await res.json();
            const tbody = document.querySelector('#files-table tbody');
            if (!data.files.length) {
                document.getElementById('empty').classList.remove('hidden');
                return;
            }
            data.files.forEach(f => {
                const size = (f.size / 1024).toFixed(1) + ' KB';
                const date = new Date(f.modified * 1000).toLocaleString();
                const viewName = f.filename.replace('.zip', '.zip');
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${f.filename}</td><td>${size}</td><td>${date}</td>
                    <td><a href="/view/${f.filename}">🔍 View</a> |
                        <a href="/download/${f.filename}">⬇ Download</a></td>`;
                tbody.appendChild(tr);
            });
        }
        load();
    </script>
</body>
</html>
'''

VIEWER_TEMPLATE = r'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>dxfvec — {{ filename }}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0f1117; color: #e1e4e8; display: flex; flex-direction: column; height: 100vh; }
        header { background: #161b22; padding: 0.75rem 1.5rem; display: flex; align-items: center;
                 gap: 1rem; border-bottom: 1px solid #30363d; flex-shrink: 0; }
        header h1 { font-size: 1rem; color: #58a6ff; white-space: nowrap; overflow: hidden;
                     text-overflow: ellipsis; max-width: 400px; }
        .toolbar { display: flex; gap: 0.5rem; margin-left: auto; }
        .btn { background: #238636; color: white; border: none; padding: 0.4rem 0.9rem;
               border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
        .btn:hover { background: #2ea043; }
        .btn-outline { background: transparent; border: 1px solid #30363d; }
        .btn-outline:hover { background: #21262d; }
        #canvas-wrap { flex: 1; overflow: hidden; position: relative; cursor: grab; }
        #canvas-wrap:active { cursor: grabbing; }
        canvas { display: block; }
        #legend { position: absolute; top: 0.75rem; right: 0.75rem; background: rgba(22,27,34,0.92);
                  border: 1px solid #30363d; border-radius: 6px; padding: 0.75rem; font-size: 0.75rem; }
        #legend .item { display: flex; align-items: center; gap: 0.5rem; margin: 0.25rem 0; }
        #legend .swatch { width: 12px; height: 12px; border-radius: 2px; border: 1px solid #555; }
        #info { position: absolute; bottom: 0.75rem; left: 0.75rem; background: rgba(22,27,34,0.92);
                border: 1px solid #30363d; border-radius: 6px; padding: 0.5rem 0.75rem;
                font-size: 0.75rem; color: #8b949e; }
        #loading { position: absolute; inset: 0; display: flex; align-items: center;
                   justify-content: center; background: #0f1117; font-size: 1rem; color: #8b949e; }
        #error-msg { display: none; position: absolute; inset: 0; align-items: center;
                     justify-content: center; background: #0f1117; color: #f85149; }
        @media print {
            header, #legend, #info, #loading, #error-msg { display: none !important; }
            #canvas-wrap { position: absolute; inset: 0; }
            canvas { max-width: 100%; max-height: 100%; }
        }
    </style>
</head>
<body>
<header>
    <h1>📐 {{ filename }}</h1>
    <div class="toolbar">
        <button class="btn" onclick="fitAll()">⊡ Fit All</button>
        <button class="btn btn-outline" onclick="zoom(1.3)">＋</button>
        <button class="btn btn-outline" onclick="zoom(0.7)">－</button>
        <button class="btn btn-outline" onclick="printDXF()" style="background:#1f6feb;border-color:#1f6feb;">🖨 Print</button>
        <button class="btn btn-outline" onclick="downloadPDF()" style="background:#9e6a03;border-color:#9e6a03;">📄 PDF</button>
        <a class="btn" href="/download/{{ filename }}" style="color:white;">⬇ Download</a>
        <a class="btn btn-outline" href="/files" style="color:#e1e4e8;">← All Files</a>
    </div>
</header>
<div id="canvas-wrap">
    <canvas id="cv"></canvas>
    <div id="loading">Loading DXF…</div>
    <div id="error-msg"></div>
    <div id="legend"></div>
    <div id="info"></div>
</div>

<script>
const API = "/api/dxf/{{ filename }}";

const LAYER_COLORS = {
    OUTLINE: "#ff0000", HOLE: "#ffffff",  LINE: "#00ff00",
    POLYGON: "#0000ff", ELLIPSE: "#00ffff", BEND: "#ff00ff",
};
const BG = "#1a1d23";
const GRID = "#252830";

let V = { entities: [], layers: [], bbox: null };
let pan = {x: 0, y: 0}, zoom = 1, dragging = null;

function hexToRgba(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${a})`;
}

async function init() {
    try {
        const res = await fetch(API);
        if (!res.ok) throw new Error(await res.text());
        V = await res.json();
        buildLegend();
        fitAll();
        draw();
        document.getElementById('loading').style.display = 'none';
    } catch (e) {
        document.getElementById('loading').style.display = 'none';
        const el = document.getElementById('error-msg');
        el.style.display = 'flex';
        el.textContent = 'Failed to load DXF: ' + e.message;
    }
}

function buildLegend() {
    const colors = {};
    const layerColors = {
        OUTLINE: "#ff0000", HOLE: "#ffffff",  LINE: "#00ff00",
        POLYGON: "#0000ff", ELLIPSE: "#00ffff", BEND: "#ff00ff",
    };
    document.getElementById('legend').innerHTML =
        Object.keys(layerColors).map(l =>
            `<div class="item"><div class="swatch" style="background:${layerColors[l]||'#888'}"></div>${l}</div>`
        ).join('');
}

function fitAll() {
    const wrap = document.getElementById('canvas-wrap');
    canvas.width = wrap.clientWidth;
    canvas.height = wrap.clientHeight;
    if (!V.bbox) { zoom = 1; pan.x = canvas.width/2; pan.y = canvas.height/2; return; }
    const {minx, miny, maxx, maxy} = V.bbox;
    const bw = maxx - minx || 1, bh = maxy - miny || 1;
    zoom = Math.min(canvas.width / (bw * 1.1), canvas.height / (bh * 1.1));
    pan.x = canvas.width / 2 - (minx + bw / 2) * zoom;
    pan.y = canvas.height / 2 + (miny + bh / 2) * zoom;
    draw();
}

function drawGrid() {
    ctx.strokeStyle = GRID;
    ctx.lineWidth = 0.5;
    if (!V.bbox) return;
    const {minx, miny, maxx, maxy} = V.bbox;
    const step = _niceStep(maxx - minx, 10);
    const x0 = Math.floor(minx / step) * step;
    const y0 = Math.floor(miny / step) * step;
    for (let x = x0; x <= maxx; x += step) {
        const sx = wx(x);
        ctx.beginPath(); ctx.moveTo(sx, 0); ctx.lineTo(sx, canvas.height); ctx.stroke();
    }
    for (let y = y0; y <= maxy; y += step) {
        const sy = wy(y);
        ctx.beginPath(); ctx.moveTo(0, sy); ctx.lineTo(canvas.width, sy); ctx.stroke();
    }
    ctx.fillStyle = '#484f58';
    ctx.font = '10px monospace';
    for (let x = x0; x <= maxx; x += step)
        ctx.fillText(x, wx(x) + 2, canvas.height - 4);
    for (let y = y0; y <= maxy; y += step)
        ctx.fillText(y, 2, wy(y) - 2);
}

function _niceStep(range, maxTicks) {
    const rough = range / maxTicks;
    const mag = Math.pow(10, Math.floor(Math.log10(rough)));
    const norm = rough / mag;
    let step;
    if (norm < 1.5) step = mag;
    else if (norm < 3) step = 2 * mag;
    else if (norm < 7) step = 5 * mag;
    else step = 10 * mag;
    return Math.max(step, 1e-6);
}

const LAYER_COLORS_MAP = {
    OUTLINE: "#ff0000", HOLE: "#ffffff", LINE: "#00ff00",
    POLYGON: "#0000ff", ELLIPSE: "#00ffff", BEND: "#ff00ff",
};

function draw() {
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    drawGrid();

    const lc = LAYER_COLORS_MAP;
    ctx.lineCap = 'round';

    for (const ent of V.entities) {
        const color = lc[ent.layer] || '#aaaaaa';
        ctx.strokeStyle = color;
        ctx.fillStyle = hexToRgba(color, 0.08);

        if (ent.type === 'line') {
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(wx(ent.x1), wy(ent.y1));
            ctx.lineTo(wx(ent.x2), wy(ent.y2));
            ctx.stroke();
        } else if (ent.type === 'circle') {
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.arc(wx(ent.cx), wy(ent.cy), ent.r * zoom, 0, Math.PI * 2);
            ctx.stroke();
        } else if (ent.type === 'ellipse') {
            ctx.lineWidth = 1.2;
            ctx.save();
            ctx.translate(wx(ent.cx), wy(ent.cy));
            ctx.rotate((ent.angle || 0) * Math.PI / 180);
            ctx.scale(ent.a * zoom, ent.b * zoom);
            ctx.beginPath(); ctx.arc(0, 0, 1, 0, Math.PI * 2); ctx.stroke();
            ctx.restore();
        } else if (ent.type === 'polyline') {
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ent.points.forEach((p, i) => {
                const sx = wx(p.x), sy = wy(p.y);
                i === 0 ? ctx.moveTo(sx, sy) : ctx.lineTo(sx, sy);
            });
            if (ent.closed) ctx.closePath();
            ctx.fill(); ctx.stroke();
        } else if (ent.type === 'point') {
            ctx.fillStyle = color;
            ctx.fillRect(wx(ent.x) - 2, wy(ent.y) - 2, 4, 4);
        } else if (ent.type === 'text') {
            ctx.fillStyle = color;
            ctx.font = `${Math.max(ent.height * zoom * 0.8, 8)}px monospace`;
            ctx.fillText(ent.text, wx(ent.x), wy(ent.y));
        }
    }

    const n = V.entities.length;
    const info = document.getElementById('info');
    info.textContent = `Entities: ${n}` + (V.bbox ? ` | Zoom: ${(zoom*100).toFixed(0)}%` : '');
}

function wx(x) { return x * zoom + pan.x; }
function wy(y) { return -y * zoom + pan.y; }   // flip Y so CAD-up is up
function invX(sx) { return (sx - pan.x) / zoom; }
function invY(sy) { return -(sy - pan.y) / zoom; }

function zoom(factor) {
    const cx = canvas.width / 2, cy = canvas.height / 2;
    const wx0 = invX(cx), wy0 = invY(cy);
    zoom *= factor;
    pan.x = cx - wx0 * zoom;
    pan.y = cy + wy0 * zoom;
    draw();
}

const canvas = document.getElementById('cv');
const ctx = canvas.getContext('2d');

document.getElementById('canvas-wrap').addEventListener('mousedown', e => {
    dragging = {x: e.clientX - pan.x, y: e.clientY - pan.y};
});
window.addEventListener('mousemove', e => {
    if (!dragging) return;
    pan.x = e.clientX - dragging.x; pan.y = e.clientY - dragging.y;
    draw();
});
window.addEventListener('mouseup', () => dragging = null);
canvas.addEventListener('wheel', e => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const wx0 = invX(mx), wy0 = invY(my);
    zoom *= e.deltaY < 0 ? 1.1 : 0.9;
    zoom = Math.max(0.01, Math.min(zoom, 50));
    pan.x = mx - wx0 * zoom; pan.y = my + wy0 * zoom;
    draw();
}, {passive: false});

window.addEventListener('resize', () => { fitAll(); });

function printDXF() {
    window.print();
}

function downloadPDF() {
    const scale = 3;
    const pw = document.getElementById('canvas-wrap');
    const pc = document.createElement('canvas');
    pc.width = pw.clientWidth * scale;
    pc.height = pw.clientHeight * scale;
    const pctx = pc.getContext('2d');
    pctx.scale(scale, scale);
    pctx.fillStyle = BG;
    pctx.fillRect(0, 0, pw.clientWidth, pw.clientHeight);
    pctx.lineCap = 'round';
    for (const ent of V.entities) {
        const color = LAYER_COLORS_MAP[ent.layer] || '#aaaaaa';
        pctx.strokeStyle = color;
        pctx.lineWidth = 1.2;
        if (ent.type === 'line') {
            pctx.beginPath(); pctx.moveTo(wx(ent.x1), wy(ent.y1)); pctx.lineTo(wx(ent.x2), wy(ent.y2)); pctx.stroke();
        } else if (ent.type === 'circle') {
            pctx.beginPath(); pctx.arc(wx(ent.cx), wy(ent.cy), ent.r * zoom, 0, Math.PI * 2); pctx.stroke();
        } else if (ent.type === 'polyline') {
            pctx.beginPath();
            ent.points.forEach((p, i) => { const s = {x: wx(p.x), y: wy(p.y)}; i === 0 ? pctx.moveTo(s.x, s.y) : pctx.lineTo(s.x, s.y); });
            if (ent.closed) pctx.closePath(); pctx.stroke();
        }
    }
    pc.toBlob(blob => {
        const reader = new FileReader();
        reader.onload = function() {
            fetch('/api/pdf', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({image: reader.result})
            }).then(r => r.blob()).then(pdfBlob => {
                const a = document.createElement('a');
                a.href = URL.createObjectURL(pdfBlob);
                a.download = '{{ filename }}.pdf';
                a.click(); URL.revokeObjectURL(a.href);
            });
        };
        reader.readAsDataURL(blob);
    }, 'image/png');
}

init();
</script>
</body>
</html>
'''


@app.route("/api/pdf", methods=["POST"])
def generate_pdf():
    """Convert a canvas PNG data URL to a downloadable PDF using Pillow."""
    import base64, io
    from PIL import Image
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"error": "No image data"}), 400
    try:
        b64 = data["image"].split(",")[1] if "," in data["image"] else data["image"]
        img = Image.open(io.BytesIO(base64.b64decode(b64)))
        pdf_bytes = io.BytesIO()
        img.save(pdf_bytes, "PDF", resolution=150)
        pdf_bytes.seek(0)
        return send_file(pdf_bytes, mimetype="application/pdf",
                         as_attachment=True, download_name="dxfvec_output.pdf")
    except Exception as e:
        return jsonify({"error": f"PDF error: {e}"}), 500

def main():
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    print("\n🔧 dxfvec Web Interface")
    print(f"📂 Open http://localhost:{port}")
    print("💡 100% local — no API keys needed\n")
    app.run(host="0.0.0.0", port=port, debug=debug)

if __name__ == "__main__":
    main()
