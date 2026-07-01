"""dxfvec CLI — image vectorization and DXF conversion.

Usage:
  dxfvec convert drawing.png                                    # Classic engine (default)
  dxfvec convert drawing.png --engine advanced                  # VTracer local AI
  dxfvec convert drawing.png --engine cloud:vectorizer_ai       # BYOK cloud AI
  dxfvec convert drawing.png --engine advanced --preset logo_engrave
  dxfvec convert drawing.png --scale "64px=20mm" --mode hatch
  dxfvec modify drawing.png --rotate 90 --resize 2
  dxfvec enhance drawing.png
  dxfvec engines                                                # List available engines
  dxfvec presets                                                # List presets
  dxfvec providers                                              # List cloud providers
"""
from __future__ import annotations

import re
from pathlib import Path

import click

from .engines import ClassicEngine, AdvancedEngine, PRESETS, list_presets, apply_preset
from .cloud_providers import get_cloud_provider, list_cloud_providers, get_api_key


def parse_scale(scale_str: str) -> tuple[float, str]:
    """Parse a scale string like '64px=20mm' or '3.2' into (px_per_unit, unit)."""
    if re.fullmatch(r"\d+(\.\d+)?", scale_str):
        return float(scale_str), "mm"

    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*px\s*=\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|inch|inches)", scale_str)
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
    **kwargs,
) -> dict:
    """Build engine config dict from CLI options."""
    cfg: dict = {
        "dxf_mode": dxf_mode,
        "cnc_layers": True,
    }

    if scale:
        sf, _ = parse_scale(scale)
        cfg["scale_factor"] = sf

    # Apply preset first (lowest priority overrides)
    if preset:
        cfg = apply_preset(cfg, preset)

    # Then apply explicit CLI overrides
    if min_area != 100:
        cfg["min_area"] = min_area
    if smoothing is not None:
        cfg["simplify_tolerance"] = smoothing
    if corner is not None:
        cfg["corner_threshold"] = corner
    if noise_filter is not None:
        cfg["filter_speckle"] = noise_filter

    # Pass through any extra kwargs
    cfg.update(kwargs)
    return cfg


@click.group()
@click.version_option(package_name="dxfvec", version="1.0.0")
def cli() -> None:
    """dxfvec — 100% free image vectorization and DXF conversion.

    Three engines:
      classic  (default)  Local OpenCV contour tracing — no API keys
      advanced           Local VTracer AI-style vectorization — no API keys
      cloud:<provider>   External AI APIs — BYOK keys required

    Supported cloud providers: vectorizer_ai, dxfai
    """


@cli.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--engine", "-e",
    default="classic",
    show_default=True,
    help=(
        "Vectorization engine: 'classic' (local OpenCV, default), "
        "'advanced' (local VTracer), or 'cloud:<provider>' (BYOK). "
        "Available cloud providers: vectorizer_ai, dxfai"
    ),
)
@click.option(
    "--mode", "-m",
    default="lines",
    type=click.Choice(["lines", "hatch", "faces"]),
    show_default=True,
    help="DXF output mode: lines (cut paths), hatch (engrave fills), faces (closed shapes).",
)
@click.option(
    "--preset", "-P",
    default=None,
    type=click.Choice(["logo_engrave", "laser_stencil", "technical_drawing", "contour_map"]),
    help="Optimization preset for the target use case.",
)
@click.option(
    "--scale", "-s",
    default=None,
    help="Pixel-to-real-world scale. Format: 'Npx=Nmm' (e.g. '64px=20mm') or direct ratio (e.g. '3.2').",
)
@click.option(
    "--output-dir", "-o",
    default="./output",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Directory for output files.",
)
@click.option(
    "--min-area", "-a",
    default=100,
    show_default=True,
    help="Minimum contour area in pixels.",
)
@click.option(
    "--smoothing",
    default=None,
    type=float,
    help="Smoothing / curve simplification tolerance (default: 1.5).",
)
@click.option(
    "--corner",
    default=None,
    type=float,
    help="Corner sensitivity threshold (0-180, higher = sharper corners).",
)
@click.option(
    "--noise-filter",
    default=None,
    type=int,
    help="Noise filtering level (1-10, higher = more speckle removal).",
)
def convert(
    image: Path,
    engine: str,
    mode: str,
    preset: str | None,
    scale: str | None,
    output_dir: Path,
    min_area: int,
    smoothing: float | None,
    corner: float | None,
    noise_filter: int | None,
) -> None:
    """Convert a raster image to DXF using the selected engine."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scale_str = "no scale"
    if scale:
        sf, _ = parse_scale(scale)
        scale_str = f"scale={sf:.4f} px/mm"

    cfg = build_config(
        engine=engine,
        dxf_mode=mode,
        preset=preset,
        scale=scale,
        min_area=min_area,
        smoothing=smoothing,
        corner=corner,
        noise_filter=noise_filter,
    )

    # Select engine
    if engine.startswith("cloud:"):
        provider_name = engine.split(":", 1)[1]
        provider = get_cloud_provider(provider_name)
        if provider is None:
            click.echo(click.style(
                f"ERROR: Unknown cloud provider '{provider_name}'. "
                "Available: vectorizer_ai, dxfai", fg="red"))
            raise click.ClickException(1)
        if not provider.is_available():
            click.echo(click.style(
                f"ERROR: {provider.display_name} is not configured. "
                f"Set the {provider.env_var} environment variable.", fg="red"))
            raise click.ClickException(1)

        click.echo(f"\n[CONVERT] {image.name} -> DXF   [{provider.display_name} BYOK, {scale_str}]")
        click.echo(f"Output: {output_dir.resolve()}\n")
        result = provider.convert(image, output_dir, cfg)

    elif engine == "advanced":
        click.echo(f"\n[CONVERT] {image.name} -> DXF   [VTracer advanced, {scale_str}]")
        click.echo(f"Output: {output_dir.resolve()}\n")
        eng = AdvancedEngine()
        result = eng.convert(image, output_dir, cfg)

    else:  # classic (default)
        click.echo(f"\n[CONVERT] {image.name} -> DXF   [classic local, {scale_str}]")
        click.echo(f"Output: {output_dir.resolve()}\n")
        eng = ClassicEngine()
        result = eng.convert(image, output_dir, cfg)

    click.echo(f"Saved DXF:    {result['dxf']}")
    click.echo(f"Saved Review: {result['review']}")
    stats = result.get("stats", {})
    click.echo(f"\nStats: {stats.get('outlines', 0)} outlines, "
               f"{stats.get('holes', 0)} holes, "
               f"{stats.get('lines', 0)} lines, "
               f"{stats.get('polygons', 0)} polygons")
    click.echo(f"Engine: {result.get('engine', engine)}")


@cli.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--rotate", "-r", type=float, help="Rotate image by N degrees.")
@click.option("--resize", "-rs", type=float, help="Resize by scale factor (0.5 = half, 2.0 = double).")
@click.option("--resize-width", "-w", type=int, help="Resize to specific width in pixels.")
@click.option("--resize-height", "-h", type=int, help="Resize to specific height in pixels.")
@click.option("--enhance/--no-enhance", default=False, help="Enhance contrast (CLAHE).")
@click.option("--denoise/--no-denoise", default=False, help="Remove noise.")
@click.option("--sharpen/--no-sharpen", default=False, help="Sharpen image.")
@click.option("--deskew/--no-deskew", default=False, help="Correct rotation/skew.")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file path.")
def modify(
    image: Path, rotate: float | None, resize: float | None,
    resize_width: int | None, resize_height: int | None,
    enhance: bool, denoise: bool, sharpen: bool, deskew: bool,
    output: Path | None,
) -> None:
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
        click.echo(f"  * Enhanced contrast")
    if denoise:
        img = modifier.denoise(img)
        click.echo(f"  * Denoised")
    if sharpen:
        img = modifier.sharpen(img)
        click.echo(f"  * Sharpened")
    if deskew:
        img, angle = modifier.deskew(img)
        click.echo(f"  * Deskewed ({angle:.2f} degrees)")

    if output is None:
        output = image.parent / f"{image.stem}_modified{image.suffix}"

    cv2.imwrite(str(output), img)
    click.echo(f"\nSaved: {output}")


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
    click.echo(f"  * Binarized")
    click.echo(f"\nSaved: {output_dir / 'enhanced.png'}")
    click.echo(f"Saved: {output_dir / 'binary.png'}")


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

    try:
        from .engines import PRESETS
        click.echo("Available presets:")
        for name, p in PRESETS.items():
            click.echo(f"  {name:<20} {p['description']}")
    except ImportError:
        pass


@cli.command()
def presets() -> None:
    """List available optimization presets."""
    try:
        from .engines import list_presets
        presets_data = list_presets()
    except ImportError:
        presets_data = {}

    click.echo("\nAvailable presets:\n")
    click.echo(f"{'Name':<20} {'Description'}")
    click.echo("-" * 60)
    for name, p in presets_data.items():
        click.echo(f"{name:<20} {p['description']}")
        click.echo(f"  min_area={p['min_area']}, smoothing={p['smoothing']}, "
                   f"corner={p['corner_threshold']}, noise={p['noise_filter']}")


@cli.command()
def providers() -> None:
    """List cloud AI providers and their configuration status."""
    click.echo("\nCloud AI providers (BYOK — Bring Your Own Key):\n")

    cloud_providers = list_cloud_providers()
    if not cloud_providers:
        click.echo("  No cloud providers available.")
        return

    for p in cloud_providers:
        status = click.style("✓ configured", fg="green") if p["available"] else click.style("✗ not configured", fg="yellow")
        click.echo(f"  {p['name']:<20} {p['display_name']}")
        click.echo(f"  {'':20} Status: {status}")
        click.echo(f"  {'':20} Env var: {p['env_var']}")
        click.echo()


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
