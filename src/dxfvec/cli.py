"""dxfvec CLI — image vectorization and DXF conversion.

Usage:
  dxfvec convert drawing.png                          # Local, free, no API
  dxfvec convert drawing.png --scale "64px=20mm"     # With real-world scale
  dxfvec modify drawing.png --rotate 90 --resize 2   # Image modification
  dxfvec enhance drawing.png                          # Enhance scanned drawings
  dxfvec providers                                    # List AI providers (optional)
"""
from __future__ import annotations

import re
from pathlib import Path

import click


def parse_scale(scale_str: str) -> tuple[float, str]:
    """Parse a scale string like '64px=20mm' or '3.2' into (px_per_unit, unit).
    
    Returns:
        (pixels_per_mm, unit_name) where unit_name is 'mm', 'cm', 'in', etc.
    
    Raises:
        click.BadParameter if the format is invalid.
    """
    # Direct ratio: "3.2" means 3.2 pixels per mm
    if re.fullmatch(r"\d+(\.\d+)?", scale_str):
        return float(scale_str), "mm"
    
    # Explicit: "64px=20mm"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*px\s*=\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|inch|inches)", scale_str)
    if m:
        px = float(m.group(1))
        real = float(m.group(2))
        unit = m.group(3)
        if unit in ("in", "inch", "inches"):
            real *= 25.4  # convert inches to mm
            unit = "mm"
        elif unit == "cm":
            real *= 10  # convert cm to mm
            unit = "mm"
        return px / real, "mm"
    
    raise click.BadParameter(
        f"Invalid scale format: '{scale_str}'. "
        "Use 'Npx=Nmm' (e.g. '64px=20mm') or a direct ratio (e.g. '3.2')."
    )


@click.group()
@click.version_option(package_name="dxfvec")
def cli() -> None:
    """dxfvec — 100% free image vectorization and DXF conversion."""


@cli.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--scale", "-s",
    default=None,
    help=(
        "Pixel-to-real-world scale. Format: 'Npx=Nmm' (e.g. '64px=20mm') or "
        "direct ratio in px/mm (e.g. '3.2'). Without this, DXF uses pixel coordinates."
    ),
)
@click.option(
    "--output-dir", "-o",
    default="./output",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Directory for output files (drawing.dxf, review.md, etc.).",
)
@click.option(
    "--min-area", "-a",
    default=100,
    show_default=True,
    help="Minimum contour area (pixels) to detect.",
)
def convert(image: Path, scale: str | None, output_dir: Path, min_area: int) -> None:
    """Convert a raster image to DXF using local vectorization (no API)."""
    scale_factor = None
    if scale:
        scale_factor, _ = parse_scale(scale)
        click.echo(f"\n🔄  {image.name}  →  DXF   [local, scale={scale_factor:.4f} px/mm]")
    else:
        click.echo(f"\n🔄  {image.name}  →  DXF   [local, no API]")
    click.echo(f"📂  Output: {output_dir.resolve()}\n")
    
    from .vectorizer import vectorize_image
    result = vectorize_image(image, output_dir, scale_factor=scale_factor, min_area=min_area)
    
    click.echo(f"✅  DXF:    {result['dxf']}")
    click.echo(f"✅  Review: {result['review']}")
    click.echo(f"\n📊  Detected: {result['stats']['outlines']} outlines, "
               f"{result['stats']['holes']} holes, {result['stats']['lines']} lines, "
               f"{result['stats']['polygons']} polygons")


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
def modify(image: Path, rotate: float | None, resize: float | None, 
           resize_width: int | None, resize_height: int | None,
           enhance: bool, denoise: bool, sharpen: bool, deskew: bool, 
           output: Path | None) -> None:
    """Modify an image (rotate, resize, enhance, denoise, sharpen, deskew)."""
    from .vectorizer import ImageModifier
    
    click.echo(f"\n🔧  Modifying: {image.name}")
    
    modifier = ImageModifier()
    img = modifier.load(image)
    
    if rotate:
        img = modifier.rotate(img, rotate)
        click.echo(f"  ✓ Rotated {rotate}°")
    
    if resize:
        img = modifier.resize(img, scale=resize)
        click.echo(f"  ✓ Resized {resize}x")
    
    if resize_width:
        img = modifier.resize(img, width=resize_width)
        click.echo(f"  ✓ Resized to {resize_width}px wide")
    
    if resize_height:
        img = modifier.resize(img, height=resize_height)
        click.echo(f"  ✓ Resized to {resize_height}px tall")
    
    if enhance:
        img = modifier.enhance_contrast(img)
        click.echo(f"  ✓ Enhanced contrast")
    
    if denoise:
        img = modifier.denoise(img)
        click.echo(f"  ✓ Denoised")
    
    if sharpen:
        img = modifier.sharpen(img)
        click.echo(f"  ✓ Sharpened")
    
    if deskew:
        img, angle = modifier.deskew(img)
        click.echo(f"  ✓ Deskewed ({angle:.2f}°)")
    
    if output is None:
        output = image.parent / f"{image.stem}_modified{image.suffix}"
    
    import cv2
    cv2.imwrite(str(output), img)
    click.echo(f"\n✅  Saved: {output}")


@cli.command()
@click.argument("image", type=click.Path(exists=True, path_type=Path))
@click.option("--output-dir", "-o", default="./output", show_default=True, type=click.Path(path_type=Path))
def enhance(image: Path, output_dir: Path) -> None:
    """Enhance a scanned drawing for better vectorization."""
    from .vectorizer import ImageModifier
    import cv2
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"\n✨  Enhancing: {image.name}")
    
    modifier = ImageModifier()
    img = modifier.load(image)
    
    # Full enhancement pipeline
    enhanced = modifier.enhance_contrast(img)
    enhanced = modifier.sharpen(enhanced)
    deskewed, angle = modifier.deskew(enhanced)
    denoised = modifier.denoise(deskewed)
    binary = modifier.binarize(denoised, method="adaptive")
    
    cv2.imwrite(str(output_dir / "enhanced.png"), denoised)
    cv2.imwrite(str(output_dir / "binary.png"), binary)
    
    click.echo(f"  ✓ Enhanced (deskewed {angle:.2f}°)")
    click.echo(f"  ✓ Binarized")
    click.echo(f"\n✅  Saved: {output_dir / 'enhanced.png'}")
    click.echo(f"✅  Saved: {output_dir / 'binary.png'}")


@cli.command()
def providers() -> None:
    """List AI providers (optional, for advanced vision analysis)."""
    from .providers import PROVIDER_MODELS
    click.echo("\nSupported AI providers (optional, for advanced analysis):\n")
    for name, model in PROVIDER_MODELS.items():
        click.echo(f"  {name:<12}  →  {model}")
    click.echo(
        "\n  Note: These require API keys and are NOT needed for basic vectorization.\n"
        "  Use 'dxfvec convert' for free, local processing.\n"
    )


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
