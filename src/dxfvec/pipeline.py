"""Single-agent DXF conversion pipeline.

Uses one vision LLM call (any provider via LiteLLM) to extract geometry,
then writes the DXF with ezdxf. Fast and straightforward.

For the multi-agent CrewAI variant, see crew_pipeline.py.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .dxf_writer import create_dxf
from .preprocess import preprocess
from .providers import vision_call

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
    """Extract JSON from LLM response with multiple fallback strategies."""
    if not text:
        raise ValueError(f"Vision LLM ({provider}) returned empty response")
    
    # Strategy 1: Strip markdown code blocks
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```\s*", "", cleaned)
    
    # Strategy 2: Find outermost braces
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    
    if start != -1 and end != -1 and end > start:
        json_str = cleaned[start:end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Fix trailing commas
            fixed = re.sub(r",\s*([}\]])", r"\1", json_str)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
    
    # Strategy 3: Try to find ANY valid JSON object in the text
    for match in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL):
        candidate = match.group()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    
    # Strategy 4: Last resort - try to fix common issues
    # Remove any non-JSON text before/after
    lines = text.split("\n")
    json_lines = []
    in_json = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("{"):
            in_json = True
        if in_json:
            json_lines.append(line)
        if in_json and stripped.endswith("}"):
            break
    
    if json_lines:
        json_str = "\n".join(json_lines)
        # Fix trailing commas
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # Strategy 5: Try to repair truncated JSON by adding missing closing brackets
    if start != -1:
        json_str = cleaned[start:]
        # Count opening and closing brackets
        open_braces = json_str.count("{")
        close_braces = json_str.count("}")
        open_brackets = json_str.count("[")
        close_brackets = json_str.count("]")
        
        # Add missing closing brackets
        while close_brackets < open_brackets:
            json_str += "]"
            close_brackets += 1
        while close_braces < open_braces:
            json_str += "}"
            close_braces += 1
        
        # Fix trailing commas
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    raise ValueError(
        f"Vision LLM ({provider}) did not return valid JSON.\n"
        f"Response saved to: raw_response.txt\n"
        f"Response (first 500 chars):\n{text[:500]}"
    )
def _scale_geometry(geometry: dict, factor: float) -> dict:
    """Scale all coordinates in geometry dict by factor (px/mm → mm).

    Applies to: outlines points, holes center/radius, bend_lines points,
    dimensions positions. Dimension text is left untouched.
    """
    scaled = json.loads(json.dumps(geometry))  # deep copy

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
    
    # Save raw response for debugging
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
