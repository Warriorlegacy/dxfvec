"""Single-agent DXF conversion pipeline.

Uses one vision LLM call (any provider via LiteLLM) to extract geometry,
then writes the DXF with ezdxf. Fast and straightforward.

For the multi-agent CrewAI variant, see crew_pipeline.py.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

from .dxf_writer import create_dxf
from .preprocess import preprocess
from .providers import vision_call

__all__ = ["convert"]

GEOMETRY_PROMPT = """
Analyze this preprocessed engineering drawing image. Extract all geometry and return a SINGLE JSON object — no prose, no markdown fences.

Required JSON structure:
{
  "outlines": [{"points": [[x, y], ...], "closed": true}],
  "holes":    [{"cx": float, "cy": float, "r": float}],
  "bend_lines": [{"points": [[x, y], ...]}],
  "dimensions": [{"x": float, "y": float, "text": "value with units"}],
  "ambiguities": ["describe anything you cannot determine clearly"],
  "confidence": "high" | "medium" | "low"
}

Rules:
- Use pixel coordinates (origin = top-left of image).
- "outlines": closed contours forming the part boundary or interior cutouts (non-circular).
- "holes": circular or elliptical apertures only — use the pixel-space centre and radius.
- "bend_lines": dashed or dotted lines (fold/bend indicators) only.
- "dimensions": any visible measurement text (e.g. "150mm", "Ø20").
- "ambiguities": list EVERY element you are unsure about; omit it from geometry.
- "confidence": your overall assessment of extraction quality.

Only include what you can clearly see. Never invent dimensions.
"""


def _extract_json(text: str, provider: str) -> dict:
    """Extract JSON geometry from LLM response text using multiple strategies."""
    if not text:
        raise ValueError(f"Vision LLM ({provider}) returned empty response")

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Strategy 2: Find JSON object boundaries
    cleaned = text.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except (json.JSONDecodeError, TypeError):
            pass

    # Strategy 3: Find ```json blocks
    json_blocks = re.findall(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    for block in json_blocks:
        try:
            return json.loads(block)
        except (json.JSONDecodeError, TypeError):
            continue

    # Strategy 4: Find lines that look like JSON
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                return json.loads(stripped)
            except (json.JSONDecodeError, TypeError):
                continue

    # Strategy 5: Find key geometry patterns and try boundary extraction
    if '"outlines"' in text and '"points"' in text and start != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except (json.JSONDecodeError, TypeError):
            pass

    raise ValueError(
        f"Vision LLM ({provider}) did not return valid JSON.\n"
        f"Response (first 500 chars):\n{text[:500]}"
    )
def _scale_geometry(geometry: dict, factor: float) -> dict:
    """Scale all coordinates in geometry dict by factor (px/mm → mm).

    Applies to: outlines points, holes center/radius, bend_lines points,
    dimensions positions. Dimension text is left untouched.
    """
    scaled = copy.deepcopy(geometry)

    for outline in scaled.get("outlines", []):
        outline["points"] = [[x * factor, y * factor] for x, y in outline.get("points", [])]

    for hole in scaled.get("holes", []):
        hole["cx"] = hole.get("cx", 0) * factor
        hole["cy"] = hole.get("cy", 0) * factor
        hole["r"]  = hole.get("r", 0) * factor

    for bend in scaled.get("bend_lines", []):
        bend["points"] = [[x * factor, y * factor] for x, y in bend.get("points", [])]

    for dim in scaled.get("dimensions", []):
        dim["x"] = dim.get("x", 0) * factor
        dim["y"] = dim.get("y", 0) * factor

    return scaled


def convert(
    image_path: str | Path,
    output_dir: str | Path,
    provider: str = "anthropic",
    scale_factor: float | None = None,
) -> dict:
    """
    Full pipeline: raster image → DXF + review.md

    Args:
        scale_factor: pixels per mm. If None, DXF uses raw pixel coordinates.

    Returns:
        dict with keys: dxf, review, geometry
    """
    image_path = Path(image_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Preprocess
    preprocessed = output_dir / "preprocessed.png"
    preprocess(image_path, preprocessed)

    # 2. Vision analysis
    raw_response = vision_call(preprocessed, GEOMETRY_PROMPT, provider=provider)
    
    if os.environ.get("DXVEC_DEBUG"):
        debug_path = output_dir / "raw_response.txt"
        debug_path.write_text(raw_response or "(empty)", encoding="utf-8")

    # Extract JSON with multiple strategies
    geometry = _extract_json(raw_response, provider)

    # 3. Apply scale if provided
    if scale_factor is not None:
        geometry = _scale_geometry(geometry, scale_factor)

    # 4. Generate DXF
    dxf_path = output_dir / "drawing.dxf"
    create_dxf(geometry, dxf_path)

    # 5. Write review report
    review_path = output_dir / "review.md"
    _write_review(geometry, image_path.name, provider, review_path, scale_factor)

    return {
        "dxf":      str(dxf_path),
        "review":   str(review_path),
        "geometry": geometry,
    }


def _write_review(
    geometry: dict,
    source_name: str,
    provider: str,
    output_path: Path,
    scale_factor: float | None = None,
) -> None:
    outlines   = geometry.get("outlines", [])
    holes      = geometry.get("holes", [])
    bends      = geometry.get("bend_lines", [])
    dims       = geometry.get("dimensions", [])
    ambiguities = geometry.get("ambiguities", [])
    confidence  = geometry.get("confidence", "unknown")

    coord_mode = f"{scale_factor:.4f} px/mm (real units)" if scale_factor else "pixel space"

    lines = [
        f"# DXF Vectorization Review — {source_name}",
        f"\n**Provider:** `{provider}`  |  **Confidence:** {confidence}  |  **Coords:** {coord_mode}",
        "\n## Geometry extracted\n",
        "| Entity type        | Count | Layer |",
        "|--------------------|-------|-------|",
        f"| Part outlines      | {len(outlines):>5} | CUT   |",
        f"| Holes / apertures  | {len(holes):>5} | CUT   |",
        f"| Bend / fold lines  | {len(bends):>5} | BEND  |",
        f"| Dimension text     | {len(dims):>5} | DIM   |",
    ]

    if not bends:
        lines.append("\nno bend lines detected")

    if ambiguities:
        lines += ["\n## Engineer must verify\n"]
        for item in ambiguities:
            lines.append(f"- {item}")
    else:
        lines.append("\n## No ambiguities flagged")

    output_path.write_text("\n".join(lines), encoding="utf-8")
