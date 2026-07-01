"""Cloud AI provider implementations for dxfvec BYOK model.

Each provider wraps an external image→vector API:
  - VectorizerAIProvider: Vectorizer.AI HTTP API
  - DXFaiProvider: DXFai API (placeholder — API not publicly documented)

All providers require user-supplied API keys stored in environment variables.
Providers are disabled by default and surfaced only when keys are configured.
"""
from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import requests

from .dxf_writer import create_dxf


# ── Environment variable key names ────────────────────────────────────────────

ENV_KEYS: dict[str, str] = {
    "vectorizer_ai": "DXVEC_VECTORIZER_AI_API_ID",
    "dxfai": "DXVEC_DXFAI_API_KEY",
}


def get_api_key(provider: str) -> str | None:
    """Retrieve API key for a provider from environment variables."""
    env_var = ENV_KEYS.get(provider.lower())
    if env_var:
        return os.environ.get(env_var)
    return None


def list_configured_providers() -> list[str]:
    """Return list of providers that have API keys configured."""
    configured = []
    for provider, env_var in ENV_KEYS.items():
        if os.environ.get(env_var):
            configured.append(provider)
    return configured


# ── Base Cloud provider ───────────────────────────────────────────────────────

class CloudProviderBase:
    """Base class for cloud AI vectorization providers."""

    provider_name: str = "base"
    display_name: str = "Cloud AI Provider"
    requires_key: bool = True
    env_var: str = ""

    def is_available(self) -> bool:
        """Return True if the required API key is configured."""
        return bool(os.environ.get(self.env_var))

    def convert(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convert image using the cloud provider API.

        Args:
            image_path: Path to input image.
            output_dir: Directory for outputs.
            config: Configuration (dxf_mode, scale_factor, etc.)

        Returns:
            dict with dxf, review, geometry, engine, stats
        """
        if not self.is_available():
            raise RuntimeError(
                f"{self.display_name} requires API key in {self.env_var}"
            )
        return self._do_convert(image_path, output_dir, config or {})

    @abstractmethod
    def _do_convert(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def _save_and_dxf(
        self,
        svg_content: str | bytes,
        output_dir: Path,
        dxf_mode: str,
        engine_name: str,
        scale_factor: float | None = None,
    ) -> dict[str, Any]:
        """Common helper: save SVG, parse to geometry, write DXF."""
        dxf_path = output_dir / "drawing.dxf"
        review_path = output_dir / "review.md"

        # Save SVG
        svg_path = output_dir / "cloud_output.svg"
        if isinstance(svg_content, bytes):
            svg_path.write_bytes(svg_content)
        else:
            svg_path.write_text(svg_content, encoding="utf-8")

        # Parse SVG → geometry
        from .engines import _svg_to_geometry
        geometry = _svg_to_geometry(svg_path, scale_factor)

        # Create DXF
        create_dxf(geometry, dxf_path)

        # Write review
        lines = [
            f"# DXF Vectorization Review — {Path(output_dir).name}",
            f"\n**Engine:** {engine_name}  |  **Provider:** {self.display_name}",
            "\n## Geometry extracted\n",
            "| Entity  | Count | Layer |",
            "|---------|-------|-------|",
            f"| Outlines| {len(geometry.get('outlines', [])):>5} | CUT   |",
            f"| Holes   | {len(geometry.get('holes', [])):>5} | CUT   |",
            f"| Polygons| {len(geometry.get('polygons', [])):>5} | ENGRAVE |",
            "\n## Provider info\n",
            f"- **{self.display_name}**: cloud API (BYOK)",
            f"- API key configured: {'yes' if self.is_available() else 'no'}",
            "- DXF layers: CUT / ENGRAVE",
        ]
        review_path.write_text("\n".join(lines), encoding="utf-8")

        return {
            "dxf": str(dxf_path),
            "review": str(review_path),
            "geometry": geometry,
            "engine": engine_name,
            "dxf_mode": dxf_mode,
            "provider": self.provider_name,
        }

    def _save_dxf_directly(
        self,
        dxf_content: bytes,
        output_dir: Path,
        dxf_mode: str,
        engine_name: str,
        scale_factor: float | None = None,
    ) -> dict[str, Any]:
        """Save DXF directly, parse its entities to estimate geometry count, and write review."""
        dxf_path = output_dir / "drawing.dxf"
        dxf_path.write_bytes(dxf_content)
        review_path = output_dir / "review.md"

        outlines_count = 0
        holes_count = 0
        polygons_count = 0
        lines_count = 0
        geometry = {"outlines": [], "holes": [], "bend_lines": [], "dimensions": []}

        try:
            import ezdxf
            doc = ezdxf.readfile(str(dxf_path))
            msp = doc.modelspace()
            for ent in msp:
                t = ent.dxftype()
                if t == "LWPOLYLINE":
                    outlines_count += 1
                elif t == "CIRCLE":
                    holes_count += 1
                elif t == "LINE":
                    lines_count += 1
                elif t in ("POLYLINE", "SOLID"):
                    polygons_count += 1
        except Exception:
            pass

        # Write review
        lines = [
            f"# DXF Vectorization Review — {Path(output_dir).name}",
            f"\n**Engine:** {engine_name}  |  **Provider:** {self.display_name}",
            "\n## Geometry extracted\n",
            "| Entity  | Count | Layer |",
            "|---------|-------|-------|",
            f"| Outlines| {outlines_count:>5} | CUT   |",
            f"| Holes   | {holes_count:>5} | CUT   |",
            f"| Lines   | {lines_count:>5} | LINE  |",
            f"| Polygons| {polygons_count:>5} | ENGRAVE |",
            "\n## Provider info\n",
            f"- **{self.display_name}**: cloud API (BYOK)",
            f"- API key configured: {'yes' if self.is_available() else 'no'}",
            "- DXF layers: CUT / ENGRAVE",
        ]
        review_path.write_text("\n".join(lines), encoding="utf-8")

        return {
            "dxf": str(dxf_path),
            "review": str(review_path),
            "geometry": geometry,
            "engine": engine_name,
            "dxf_mode": dxf_mode,
            "provider": self.provider_name,
            "stats": {
                "outlines": outlines_count,
                "holes": holes_count,
                "lines": lines_count,
                "polygons": polygons_count,
            }
        }


# ── Vectorizer.AI provider ───────────────────────────────────────────────────

class VectorizerAIProvider(CloudProviderBase):
    """Vectorizer.AI cloud API provider.

    Requires environment variable: DXVEC_VECTORIZER_AI_API_ID
    (and optionally DXVEC_VECTORIZER_AI_API_SECRET for authentication)

    API docs: https://vectorizer.ai/api
    """

    provider_name = "vectorizer_ai"
    display_name = "Vectorizer.AI"
    env_var = ENV_KEYS["vectorizer_ai"]
    api_base = "https://vectorizer.ai/api/v1"

    def _do_convert(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = Path(image_path)

        api_id = os.environ.get("DXVEC_VECTORIZER_AI_API_ID", "")
        api_secret = os.environ.get("DXVEC_VECTORIZER_AI_API_SECRET", "")

        if not api_id:
            raise RuntimeError(
                "Vectorizer.AI requires DXVEC_VECTORIZER_AI_API_ID environment variable"
            )

        dxf_mode = config.get("dxf_mode", "lines")
        scale_factor = config.get("scale_factor")

        # Read image
        image_data = image_path.read_bytes()
        filename = image_path.name

        # Prepare request
        auth = (api_id, api_secret) if api_secret else (api_id, "")
        files = {"image": (filename, image_data, _guess_mime(filename))}

        # Request DXF output directly
        data = {
            "output_format": "dxf",
            "colormode": "binary",
        }

        try:
            response = requests.post(
                f"{self.api_base}/vectorize",
                auth=auth,
                files=files,
                data=data,
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Vectorizer.AI API error: {e}")

        # Save and return using the DXF-direct helper
        return self._save_dxf_directly(
            response.content, output_dir, dxf_mode,
            engine_name="cloud:vectorizer_ai", scale_factor=scale_factor,
        )


def _guess_mime(filename: str) -> str:
    ext = filename.lower().split(".")[-1]
    mimes = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "tiff": "image/tiff",
        "tif": "image/tiff",
    }
    return mimes.get(ext, "image/png")


# ── DXFai provider ────────────────────────────────────────────────────────────

class DXFaiProvider(CloudProviderBase):
    """DXFai cloud API provider.

    Requires environment variable: DXVEC_DXFAI_API_KEY

    Note: DXFai's public API documentation is not widely available.
    This provider implements a best-effort integration based on their
    public web service. If the API format changes, update the endpoint
    and request format accordingly.
    """

    provider_name = "dxfai"
    display_name = "DXFai"
    env_var = ENV_KEYS["dxfai"]
    api_base = "https://dxfai.ai/api"

    def _do_convert(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = Path(image_path)

        api_key = os.environ.get(self.env_var, "")

        if not api_key:
            raise RuntimeError(
                f"DXFai requires {self.env_var} environment variable"
            )

        dxf_mode = config.get("dxf_mode", "lines")
        scale_factor = config.get("scale_factor")

        image_data = image_path.read_bytes()

        try:
            response = requests.post(
                f"{self.api_base}/convert",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/octet-stream",
                },
                data=image_data,
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"DXFai API error: {e}")

        return self._save_dxf_directly(
            response.content, output_dir, dxf_mode,
            engine_name="cloud:dxfai", scale_factor=scale_factor,
        )


# ── Provider registry ────────────────────────────────────────────────────────

CLOUD_PROVIDERS: dict[str, type[CloudProviderBase]] = {
    "vectorizer_ai": VectorizerAIProvider,
    "dxfai": DXFaiProvider,
}


def get_cloud_provider(name: str) -> CloudProviderBase | None:
    """Get a cloud provider instance by name.

    Returns None if the provider doesn't exist.
    The provider will still need valid API keys to function.
    """
    cls = CLOUD_PROVIDERS.get(name.lower())
    if cls is None:
        return None
    return cls()


def list_cloud_providers() -> list[dict[str, Any]]:
    """List available cloud providers with availability status."""
    result = []
    for name, cls in CLOUD_PROVIDERS.items():
        instance = cls()
        result.append({
            "name": name,
            "display_name": instance.display_name,
            "available": instance.is_available(),
            "env_var": instance.env_var,
            "requires_key": instance.requires_key,
        })
    return result
