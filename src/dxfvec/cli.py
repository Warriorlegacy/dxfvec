"""dxfvec CLI — image vectorization and DXF conversion.

Usage:
  dxfvec convert drawing.png                                    # Classic engine (default)
  dxfvec convert drawing.png --engine advanced                  # VTracer local AI
  dxfvec convert drawing.png --engine cloud:vectorizer_ai       # BYOK cloud AI
  dxfvec convert drawing.png --tolerance-mm 0.1 --detect-arcs
  dxfvec convert drawing.png --dxf-version R2010 --units mm
  dxfvec batch ./drawings/ --format zip                         # Batch mode
  dxfvec modify drawing.png --rotate 90 --resize 2
  dxfvec enhance drawing.png
  dxfvec engines                                                # List available engines
  dxfvec presets                                                # List presets
  dxfvec providers                                              # List cloud providers
"""
from __future__ import annotations

import csv
import json
import re
import zipfile
from pathlib import Path

import click

from .engines import ClassicEngine, AdvancedEngine, PRESETS, list_presets, apply_preset
from .cloud_providers import get_cloud_provider, list_cloud_providers


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}


def parse_scale(scale_str: str) -> tuple[float, str]:
    """Parse a scale string like '64px=20mm' or '3.2' into (px_per_unit, unit)."""
    if re.fullmatch(r"\d+(\.\d+)?", scale_str):
        return float(scale_str), "mm"

    m = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*px\s*=\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|inch|inches)",
        scale_str,
    )
    if m:
        px = float(m.group(1))
        real = float(m.group(2))
        unit = m.group(3)
        if unit in ("in", "inch", "inches"):
            real *= 25.4
            unit = "mm"
        elif unit == "cm":
            real *= 10
            unit = "mm"
        return px / real, "mm"

    raise click.BadParameter(
        f"Invalid scale format: '{scale_str}'. "
        "Use 'Npx=Nmm' (e.g. '64px=20mm') or a direct ratio (e.g. '3.2')."
    )


def build_config(
    engine: str,
    dxf_mode: str,
    preset: str | None,
    scale: str | None,
    min_area: int,
    smoothing: float | None,
    corner: float | None,
    noise_filter: int | None,
    tolerance_mm: float | None = None,
    dxf_version: str = "R2010",
    units: str = "mm",
    trace_mode: str = "outline",
    detect_arcs: bool = True,
    **kwargs,
) -> dict:
    """Build engine config dict from CLI options."""
    cfg: dict = {
        "dxf_mode": dxf_mode,
        "dxf_version": dxf_version,
        "trace_mode": trace_mode,
        "detect_arcs": detect_arcs,
        "cnc_layers": True,
    }

    if scale:
        sf, _ = parse_scale(scale)
        cfg["scale_factor"] = sf
    cfg["units"] = units

    if preset:
        cfg = apply_preset(cfg, preset)

    if min_area != 100:
        cfg["min_area"] = min_area
    if smoothing is not None:
        cfg["simplify_tolerance"] = smoothing
    if corner is not None:
        cfg["corner_threshold"] = corner
    if noise_filter is not None:
        cfg["filter_speckle"] = noise_filter
    if tolerance_mm is not None:
        cfg["tolerance_mm"] = tolerance_mm

    cfg.update(kwargs)
    return cfg


def _display_qa(qa: dict) -> None:
    """Print QA report summary to console."""
    status_icon = click.style("PASS", fg="green") if qa.get("dxf_audit_pass", True) else click.style("FAIL", fg="red")
    cal_icon = click.style("yes", fg="green") if qa.get("is_calibrated") else click.style("no", fg="yellow")

    click.echo("")
    click.echo("-" * 50)
    click.echo(click.style(" QA Report", bold=True))
    click.echo("-" * 50)
    click.echo(f"  Entities:     {qa.get('entity_count', 0)}")
    click.echo(f"  Closed paths: {qa.get('closed_path_count', 0)}")
    click.echo(f"  Open paths:   {qa.get('open_path_count', 0)}")
    click.echo(f"  Segments:     {qa.get('total_segments', 0)}")
    click.echo(f"  Nodes:        {qa.get('node_count', 0)}")
    click.echo(f"  Layers:       {len(qa.get('layers', []))}")
    click.echo(f"  Calibrated:   {cal_icon}")
    click.echo(f"  DXF audit:    {status_icon}")

    open_paths = qa.get("open_paths", [])
    if open_paths:
        click.echo(click.style(f"\n  WARNING {len(open_paths)} open path(s):", fg="yellow"))
        for op in open_paths[:5]:
            click.echo(f"    Path #{op['path_index']}: gap {op['gap_mm']:.2f}mm")
        if len(open_paths) > 5:
            click.echo(f"    ... and {len(open_paths) - 5} more")

    self_intersections = qa.get("self_intersections", [])
    if self_intersections:
        click.echo(click.style(f"\n  WARNING {len(self_intersections)} self-intersection(s):", fg="yellow"))
        for si in self_intersections[:3]:
            click.echo(f"    Path #{si['path_index']} at ({si['x']:.1f}, {si['y']:.1f})")

    for w in qa.get("warnings", []):
        click.echo(click.style(f"  WARNING {w}", fg="yellow"))

    layers = qa.get("layers", [])
    if layers:
        click.echo("")
        for l in layers:
            c = f"C{l['color_aci']}" if l.get("color_aci") else "-"
            click.echo(f"  Layer '{l['name']}': {l['entity_count']} entities (ACI {c})")

    bb = qa.get("bounding_box", {})
    if bb:
        unit = bb.get("unit", "px")
        click.echo(f"\n  Bounding box: {bb.get('min_x', 0):.1f}, {bb.get('min_y', 0):.1f}"
                   f" -> {bb.get('max_x', 0):.1f}, {bb.get('max_y', 0):.1f} [{unit}]")
        dim_accuracy = qa.get("estimated_dimensional_accuracy_pct")
        if dim_accuracy is not None:
            acc_color = "green" if dim_accuracy >= 99 else "yellow" if dim_accuracy >= 95 else "red"
            click.echo(f"  Dimensional accuracy: {click.style(f'{dim_accuracy:.2f}%', fg=acc_color)}")
    click.echo("-" * 50)


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI Group
# ═══════════════════════════════════════════════════════════════════════════════

@click.group()
@click.version_option(package_name="dxfvec", version="2.0.0")
def cli() -> None:
    """dxfvec - 100% free image vectorization and DXF conversion.

    Three engines:

      classic  (default)  Local OpenCV contour tracing - no API keys

      advanced           Local VTracer AI-style vectorization - no API keys

      cloud:<provider>   External AI APIs - BYOK keys required
    """


# ═══════════════════════════════════════════════════════════════════════════════
#  convert
# ═══════════════════════════════════════════════════════════════════════════════

@cli.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--engine", "-e", default="classic", show_default=True,
              help="Vectorization engine: 'classic', 'advanced', or 'cloud:<provider>'.")
@click.option("--mode", "-m", default="lines",
              type=click.Choice(["lines", "hatch", "faces"]), show_default=True,
              help="DXF output mode.")
@click.option("--preset", "-P", default=None,
              type=click.Choice(["logo_engrave", "laser_stencil", "technical_drawing", "contour_map"]),
              help="Optimization preset.")
@click.option("--scale", "-s", default=None,
              help="Pixel-to-real-world scale. Format: 'Npx=Nmm' or direct ratio.")
@click.option("--output-dir", "-o", default="./output", show_default=True,
              type=click.Path(path_type=Path), help="Output directory.")
@click.option("--min-area", "-a", default=100, show_default=True, help="Minimum contour area in pixels.")
@click.option("--smoothing", default=None, type=float, help="Smoothing tolerance (default: 1.5).")
@click.option("--corner", default=None, type=float, help="Corner sensitivity (0-180).")
@click.option("--noise-filter", default=None, type=int, help="Noise filtering level (1-10).")
@click.option("--deskew-perspective", is_flag=True, default=False, help="Auto perspective correction.")
# v2.0 options
@click.option("--tolerance-mm", default=None, type=float,
              help="Node reduction tolerance in mm (default: 0.15).")
@click.option("--dxf-version", default="R2010",
              type=click.Choice(["R12", "R2010", "R2018"]), show_default=True,
              help="DXF version.")
@click.option("--units", default="mm", type=click.Choice(["mm", "cm", "in"]), show_default=True,
              help="Real-world units for DXF header.")
@click.option("--trace-mode", default="outline",
              type=click.Choice(["outline", "centerline"]), show_default=True,
              help="Trace mode.")
@click.option("--detect-arcs / --no-detect-arcs", default=True,
              help="Detect arcs/circles and emit native entities.")
@click.option("--qa / --no-qa", default=True, help="Display QA report.")
def convert(image: Path, engine: str, mode: str, preset: str | None,
            scale: str | None, output_dir: Path, min_area: int,
            smoothing: float | None, corner: float | None,
            noise_filter: int | None, deskew_perspective: bool,
            tolerance_mm: float | None, dxf_version: str, units: str,
            trace_mode: str, detect_arcs: bool, qa: bool) -> None:
    """Convert a raster image to DXF using the selected engine."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if deskew_perspective:
        import cv2
        from .preprocess import deskew_perspective as _deskew_p
        img = cv2.imread(str(image))
        if img is not None:
            warped = _deskew_p(img)
            temp_warped_path = output_dir / f"warped_{image.name}"
            cv2.imwrite(str(temp_warped_path), warped)
            image = temp_warped_path

    scale_desc = "no scale"
    if scale:
        sf, _ = parse_scale(scale)
        scale_desc = f"{sf:.4f} px/{units}"

    cfg = build_config(engine=engine, dxf_mode=mode, preset=preset,
                       scale=scale, min_area=min_area, smoothing=smoothing,
                       corner=corner, noise_filter=noise_filter,
                       tolerance_mm=tolerance_mm, dxf_version=dxf_version,
                       units=units, trace_mode=trace_mode, detect_arcs=detect_arcs)

    if engine.startswith("cloud:"):
        provider_name = engine.split(":", 1)[1]
        provider = get_cloud_provider(provider_name)
        if provider is None:
            click.echo(click.style(f"ERROR: Unknown cloud provider '{provider_name}'.", fg="red"))
            raise click.ClickException(1)
        if not provider.is_available():
            click.echo(click.style(
                f"ERROR: {provider.display_name} not configured. Set {provider.env_var}.", fg="red"))
            raise click.ClickException(1)
        click.echo(f"\n[CONVERT] {image.name}  [{provider.display_name} BYOK, {scale_desc}]")
        result = provider.convert(image, output_dir, cfg)
    elif engine == "advanced":
        click.echo(f"\n[CONVERT] {image.name}  [VTracer, {trace_mode}, DXF {dxf_version}, {scale_desc}]")
        result = AdvancedEngine().convert(image, output_dir, cfg)
    else:
        click.echo(f"\n[CONVERT] {image.name}  [Classic, {trace_mode}, DXF {dxf_version}, {scale_desc}]")
        result = ClassicEngine().convert(image, output_dir, cfg)

    click.echo(f"\n  DXF: {result.get('dxf', 'N/A')}")
    svg_path = result.get("svg")
    if svg_path:
        click.echo(f"  SVG: {svg_path}")

    stats = result.get("stats", {})
    click.echo(f"  Paths: {stats.get('paths', 0)}  Closed: {stats.get('closed', 0)}  "
               f"Open: {stats.get('open', 0)}  Nodes: {stats.get('nodes', 0)}")

    if qa and "qa_report" in result:
        qa_dict = result["qa_report"]
        if isinstance(qa_dict, dict):
            _display_qa(qa_dict)

    qa_paths = result.get("qa_report_paths", {})
    if qa_paths:
        click.echo(f"  QA JSON: {qa_paths.get('json', 'N/A')}")
        click.echo(f"  QA Markdown: {qa_paths.get('md', 'N/A')}")


# ═══════════════════════════════════════════════════════════════════════════════
#  batch
# ═══════════════════════════════════════════════════════════════════════════════

@cli.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--output-dir", "-o", default="./batch_output", show_default=True,
              type=click.Path(path_type=Path), help="Output directory.")
@click.option("--format", "-f", default="zip", type=click.Choice(["zip", "dir"]), show_default=True,
              help="Output format.")
@click.option("--engine", "-e", default="classic", show_default=True,
              help="Vectorization engine.")
@click.option("--mode", "-m", default="lines", type=click.Choice(["lines", "hatch", "faces"]), show_default=True)
@click.option("--preset", "-P", default=None,
              type=click.Choice(["logo_engrave", "laser_stencil", "technical_drawing", "contour_map"]))
@click.option("--scale", "-s", default=None)
@click.option("--tolerance-mm", default=None, type=float)
@click.option("--dxf-version", default="R2010", type=click.Choice(["R12", "R2010", "R2018"]), show_default=True)
@click.option("--units", default="mm", type=click.Choice(["mm", "cm", "in"]), show_default=True)
@click.option("--trace-mode", default="outline", type=click.Choice(["outline", "centerline"]), show_default=True)
@click.option("--detect-arcs / --no-detect-arcs", default=True)
@click.option("--recursive", "-r", is_flag=True, default=False, help="Scan subdirectories.")
@click.option("--max-files", default=0, type=int, help="Max files to process (0 = unlimited).")
def batch(input_dir: Path, output_dir: Path, format: str,
          engine: str, mode: str, preset: str | None, scale: str | None,
          tolerance_mm: float | None, dxf_version: str, units: str,
          trace_mode: str, detect_arcs: bool,
          recursive: bool, max_files: int) -> None:
    """Batch convert all images in INPUT_DIR to DXF."""
    import time

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    images: list[Path] = []
    glob_pat = "**/*" if recursive else "*"
    for f in sorted(input_dir.glob(glob_pat)):
        if f.suffix.lower() in IMAGE_EXTENSIONS and f.is_file():
            images.append(f)

    if not images:
        click.echo(click.style(f"No supported images in '{input_dir}'.", fg="yellow"))
        click.echo(f"Supported: {', '.join(sorted(IMAGE_EXTENSIONS))}")
        return

    if max_files > 0:
        images = images[:max_files]

    click.echo(f"\n[Batch] {len(images)} image(s) from '{input_dir}'")
    click.echo(f"  Engine: {engine}  DXF: {dxf_version}  Mode: {mode}  Units: {units}")
    if preset:
        click.echo(f"  Preset: {preset}")
    click.echo(f"  Output: {output_dir.resolve()}")
    click.echo("")

    base_cfg = build_config(engine=engine, dxf_mode=mode, preset=preset,
                            scale=scale, min_area=100, smoothing=None,
                            corner=None, noise_filter=None,
                            tolerance_mm=tolerance_mm, dxf_version=dxf_version,
                            units=units, trace_mode=trace_mode, detect_arcs=detect_arcs)

    eng_inst = AdvancedEngine() if engine == "advanced" else ClassicEngine()

    summary: list[dict] = []
    total_start = time.time()
    success = 0
    failed = 0

    for i, img in enumerate(images):
        click.echo(f"  [{i + 1}/{len(images)}] {img.name} ...", nl=False)
        img_out_dir = output_dir / img.stem
        img_out_dir.mkdir(parents=True, exist_ok=True)

        try:
            start = time.time()
            result = eng_inst.convert(img, img_out_dir, dict(base_cfg))
            elapsed = time.time() - start

            stats = result.get("stats", {})
            qa_rpt = result.get("qa_report", {})
            qa_pass = qa_rpt.get("dxf_audit_pass", True) if isinstance(qa_rpt, dict) else True

            summary.append({
                "file": img.name,
                "status": "done",
                "elapsed_s": round(elapsed, 2),
                "paths": stats.get("paths", 0),
                "closed": stats.get("closed", 0),
                "open": stats.get("open", 0),
                "nodes": stats.get("nodes", 0),
                "layers": stats.get("layers", 0),
                "dxf_audit_pass": qa_pass,
            })
            success += 1
            click.echo(click.style(f" done ({elapsed:.1f}s)", fg="green"))
        except Exception as e:
            summary.append({"file": img.name, "status": "failed", "error": str(e)})
            failed += 1
            click.echo(click.style(f" FAILED: {e}", fg="red"))

    total_elapsed = time.time() - total_start

    csv_path = output_dir / "summary.csv"
    json_path = output_dir / "summary.json"

    with open(str(csv_path), "w", newline="", encoding="utf-8") as f:
        if summary:
            writer = csv.DictWriter(f, fieldnames=summary[0].keys())
            writer.writeheader()
            writer.writerows(summary)

    json_path.write_text(json.dumps({
        "batch": {"total": len(images), "success": success, "failed": failed, "elapsed_s": round(total_elapsed, 2)},
        "results": summary,
    }, indent=2), encoding="utf-8")

    if format == "zip":
        zip_path = output_dir / "batch_output.zip"
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for f in output_dir.rglob("*"):
                if f.is_file() and f != zip_path and f.parent != output_dir:
                    zf.write(str(f), str(f.relative_to(output_dir)))
        click.echo(f"\n  ZIP: {zip_path}")

    click.echo("\n" + "-" * 50)
    click.echo(click.style(f" Batch complete: {success} ok, {failed} failed ({total_elapsed:.1f}s)", bold=True))
    click.echo(f"  CSV: {csv_path}\n  JSON: {json_path}")
    click.echo("-" * 50)


# ═══════════════════════════════════════════════════════════════════════════════
#  modify
# ═══════════════════════════════════════════════════════════════════════════════

@cli.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--rotate", "-r", type=float)
@click.option("--resize", "-rs", type=float)
@click.option("--resize-width", "-w", type=int)
@click.option("--resize-height", "-h", type=int)
@click.option("--enhance/--no-enhance", default=False)
@click.option("--denoise/--no-denoise", default=False)
@click.option("--sharpen/--no-sharpen", default=False)
@click.option("--deskew/--no-deskew", default=False)
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path.")
def modify(image: Path, rotate: float | None, resize: float | None,
           resize_width: int | None, resize_height: int | None,
           enhance: bool, denoise: bool, sharpen: bool, deskew: bool,
           output: Path | None) -> None:
    """Modify an image (rotate, resize, enhance, denoise, sharpen, deskew)."""
    from .vectorizer import ImageModifier
    import cv2

    click.echo(f"\n[MODIFY] {image.name}")
    modifier = ImageModifier()
    img = modifier.load(image)

    if rotate:
        img = modifier.rotate(img, rotate)
        click.echo(f"  * Rotated {rotate} degrees")
    if resize:
        img = modifier.resize(img, scale=resize)
        click.echo(f"  * Resized {resize}x")
    if resize_width:
        img = modifier.resize(img, width=resize_width)
        click.echo(f"  * Resized to {resize_width}px wide")
    if resize_height:
        img = modifier.resize(img, height=resize_height)
        click.echo(f"  * Resized to {resize_height}px tall")
    if enhance:
        img = modifier.enhance_contrast(img)
        click.echo("  * Enhanced contrast")
    if denoise:
        img = modifier.denoise(img)
        click.echo("  * Denoised")
    if sharpen:
        img = modifier.sharpen(img)
        click.echo("  * Sharpened")
    if deskew:
        img, angle = modifier.deskew(img)
        click.echo(f"  * Deskewed ({angle:.2f} degrees)")

    if output is None:
        output = image.parent / f"{image.stem}_modified{image.suffix}"
    cv2.imwrite(str(output), img)
    click.echo(f"\nSaved: {output}")


# ═══════════════════════════════════════════════════════════════════════════════
#  enhance
# ═══════════════════════════════════════════════════════════════════════════════

@cli.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--output-dir", "-o", default="./output", show_default=True, type=click.Path(path_type=Path))
def enhance(image: Path, output_dir: Path) -> None:
    """Enhance a scanned drawing for better vectorization."""
    from .vectorizer import ImageModifier
    import cv2

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"\n[ENHANCE] {image.name}")
    modifier = ImageModifier()
    img = modifier.load(image)

    enhanced = modifier.enhance_contrast(img)
    enhanced = modifier.sharpen(enhanced)
    deskewed, angle = modifier.deskew(enhanced)
    denoised = modifier.denoise(deskewed)
    binary = modifier.binarize(denoised, method="adaptive")

    cv2.imwrite(str(output_dir / "enhanced.png"), denoised)
    cv2.imwrite(str(output_dir / "binary.png"), binary)

    click.echo(f"  * Enhanced (deskewed {angle:.2f} degrees)")
    click.echo("  * Binarized")
    click.echo(f"\nSaved: {output_dir / 'enhanced.png'}")
    click.echo(f"Saved: {output_dir / 'binary.png'}")


# ═══════════════════════════════════════════════════════════════════════════════
#  engines
# ═══════════════════════════════════════════════════════════════════════════════

@cli.command()
def engines() -> None:
    """List available vectorization engines."""
    click.echo("\nAvailable engines:\n")
    click.echo("  classic        Local OpenCV contour tracing (default)")
    click.echo("                 - Always available, no API keys")
    click.echo("                 - Fast, deterministic, CNC/laser ready\n")
    click.echo("  advanced       Local VTracer AI-style vectorization")
    click.echo("                 - No API keys required")
    click.echo("                 - High-quality SVG-style paths\n")
    click.echo("  cloud:vectorizer_ai   Vectorizer.AI cloud API (BYOK)")
    click.echo("  cloud:dxfai           DXFai cloud API (BYOK)")
    click.echo("                 - Require API keys in environment variables")
    click.echo("                 - Best quality for complex images\n")

    for name, p in PRESETS.items():
        click.echo(f"  Preset '{name}': {p['description']}")


# ═══════════════════════════════════════════════════════════════════════════════
#  presets
# ═══════════════════════════════════════════════════════════════════════════════

@cli.command()
def presets() -> None:
    """List available optimization presets."""
    presets_data = list_presets()
    click.echo("\nAvailable presets:\n")
    click.echo(f"{'Name':<20} {'Description'}")
    click.echo("-" * 60)
    for name, p in presets_data.items():
        click.echo(f"{name:<20} {p['description']}")
        click.echo(f"  min_area={p['min_area']}, smoothing={p['smoothing']}, "
                   f"corner={p['corner_threshold']}, noise={p['noise_filter']}")


# ═══════════════════════════════════════════════════════════════════════════════
#  providers
# ═══════════════════════════════════════════════════════════════════════════════

@cli.command()
def providers() -> None:
    """List cloud AI providers and their configuration status."""
    click.echo("\nCloud AI providers (BYOK - Bring Your Own Key):\n")

    for p in list_cloud_providers():
        status = click.style("configured", fg="green") if p["available"] else click.style("not configured", fg="yellow")
        click.echo(f"  {p['name']:<20} {p['display_name']}")
        click.echo(f"  {'':20} Status: {status}")
        click.echo(f"  {'':20} Env var: {p['env_var']}")
        click.echo()


# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    cli()


if __name__ == "__main__":
    main()
