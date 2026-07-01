"""dxfvec — raster engineering drawings → DXF vector files.

Supports three engines:
  - Classic: local OpenCV contour tracing (no API keys)
  - Advanced: local VTracer AI-style vectorization (no API keys)
  - Cloud AI: external APIs — BYOK (Vectorizer.AI, DXFai)

Also supports:
  - Multi-agent CrewAI pipeline
  - Vision LLM pipeline (Anthropic, OpenAI, Google, etc.)
  - Web interface and CLI
"""
__version__ = "1.0.0"

from .engines import ClassicEngine, AdvancedEngine, PRESETS, list_presets, apply_preset
from .cloud_providers import (
    get_cloud_provider,
    list_cloud_providers,
    get_api_key,
    list_configured_providers,
    CLOUD_PROVIDERS,
)
from .vectorizer import vectorize_image, Vectorizer, ImageModifier, ShapeDetector, DXFGenerator
from .dxf_writer import create_dxf
from .preprocess import preprocess

__all__ = [
    # Engines
    "ClassicEngine",
    "AdvancedEngine",
    "PRESETS",
    "list_presets",
    "apply_preset",
    # Cloud providers
    "get_cloud_provider",
    "list_cloud_providers",
    "get_api_key",
    "list_configured_providers",
    "CLOUD_PROVIDERS",
    # Core vectorization
    "vectorize_image",
    "Vectorizer",
    "ImageModifier",
    "ShapeDetector",
    "DXFGenerator",
    # DXF writer
    "create_dxf",
    # Preprocessing
    "preprocess",
]
