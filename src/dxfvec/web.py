"""Web interface for dxfvec — free image vectorization.

Usage:
  python -m dxfvec.web
  # Then open http://localhost:5000
  
Production:
  gunicorn --bind 0.0.0.0:5000 --workers 2 dxfvec.web:app
"""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from flask import Flask, render_template_string, request, send_file, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Max upload size: 10MB
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

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
        <h1>dxfvec <span class="badge">100% FREE</span></h1>
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
                    <a href="/download/${data.filename}" class="download-btn">Download DXF</a>
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
    
    scale = request.form.get("scale", "").strip() or None
    min_area = int(request.form.get("min-area", 100))
    
    # Save uploaded file
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / file.filename
        file.save(str(input_path))
        
        # Parse scale
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
        
        # Convert
        from .vectorizer import vectorize_image
        output_dir = Path(tmpdir) / "output"
        
        try:
            result = vectorize_image(
                input_path, output_dir,
                scale_factor=scale_factor,
                min_area=min_area
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
        # Create zip for download
        dxf_path = Path(result["dxf"])
        zip_path = Path(tmpdir) / "result.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(dxf_path, dxf_path.name)
            zf.write(Path(result["review"]), "review.md")
        
        # Save zip for download
        download_dir = Path(tmpdir).parent / "dxfvec_downloads"
        download_dir.mkdir(exist_ok=True)
        final_zip = download_dir / f"{input_path.stem}.zip"
        final_zip.write_bytes(zip_path.read_bytes())
    
    return jsonify({
        "filename": final_zip.name,
        "stats": result["stats"]
    })

@app.route("/download/<filename>")
def download(filename):
    download_dir = Path(tempfile.gettempdir()) / "dxfvec_downloads"
    file_path = download_dir / filename
    if not file_path.exists():
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True, download_name=filename)

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
