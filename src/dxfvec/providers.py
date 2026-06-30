"""Multi-provider vision LLM abstraction via LiteLLM with automatic fallback.

Supported providers (pass to --provider):
  google    → gemini/gemini-2.5-flash  (default)
  openai    → openai/gpt-4o
  openrouter → openrouter/anthropic/claude-sonnet-4
  groq      → groq/llama-3.3-70b-versatile
  xai       → xai/grok-2
  cerebras  → cerebras/llama-3.3-70b
  mistral   → mistral/mistral-large-latest
  cohere    → cohere/command-r-plus
  nvidia    → nim/meta/llama-3.1-70b-instruct
  ollama    → ollama/llava  (local, no API key)
  azure     → azure/gpt-4o
  anthropic → anthropic/claude-opus-4-6

Any full LiteLLM model string is also accepted, e.g. "openai/gpt-4o".

Fallback chain: tries providers in order until one succeeds.
"""
from __future__ import annotations

import base64
import time
from pathlib import Path

import litellm

PROVIDER_MODELS: dict[str, str] = {
    "google":     "gemini/gemini-2.5-flash",
    "openai":     "openai/gpt-4o",
    "openrouter": "openrouter/anthropic/claude-sonnet-4",
    "groq":       "groq/llama-3.3-70b-versatile",
    "xai":        "xai/grok-2",
    "cerebras":   "cerebras/llama-3.3-70b",
    "mistral":    "mistral/mistral-large-latest",
    "cohere":     "cohere/command-r-plus",
    "nvidia":     "nim/meta/llama-3.1-70b-instruct",
    "ollama":     "ollama/llava",
    "azure":      "azure/gpt-4o",
    "anthropic":  "anthropic/claude-opus-4-6",
}

# Default fallback chain — tried in order if primary fails
FALLBACK_CHAIN: list[str] = [
    "google",
    "openrouter",
    "groq",
    "mistral",
    "openai",
    "cerebras",
    "cohere",
    "nvidia",
    "xai",
]

_MEDIA_TYPES = {
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "png":  "image/png",
    "tiff": "image/tiff",
    "tif":  "image/tiff",
    "bmp":  "image/bmp",
}


def resolve_model(provider: str) -> str:
    """Resolve a short provider name to a LiteLLM model string."""
    if "/" in provider:
        return provider  # already a full litellm string
    return PROVIDER_MODELS.get(provider.lower(), provider)


def _build_messages(image_b64: str, media_type: str, prompt: str) -> list[dict]:
    """Build the messages payload for a vision LLM call."""
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                },
                {"type": "text", "text": prompt},
            ],
        }
    ]


def vision_call(
    image_path: str | Path,
    prompt: str,
    provider: str = "google",
    temperature: float = 0.1,
    max_tokens: int = 4096,
    fallback: bool = True,
    **kwargs,
) -> str:
    """
    Call any vision-capable LLM with an image.

    Args:
        fallback: If True and primary provider fails, try the fallback chain.

    The image is base64-encoded and sent inline (data URI).
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with open(image_path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()

    ext = image_path.suffix.lower().lstrip(".")
    media_type = _MEDIA_TYPES.get(ext, "image/png")
    messages = _build_messages(b64, media_type, prompt)

    # Try primary provider
    model = resolve_model(provider)
    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content
    except Exception as e:
        if not fallback:
            raise
        print(f"  [{provider}] failed: {type(e).__name__} — trying fallback chain...")

    # Try fallback chain
    tried = {provider.lower()}
    for fb_name in FALLBACK_CHAIN:
        if fb_name in tried:
            continue
        fb_model = resolve_model(fb_name)
        try:
            print(f"  trying {fb_name} ({fb_model})...")
            response = litellm.completion(
                model=fb_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            print(f"  [{fb_name}] succeeded")
            return response.choices[0].message.content
        except Exception as e:
            tried.add(fb_name)
            print(f"  [{fb_name}] failed: {type(e).__name__}")
            continue

    raise RuntimeError(f"All providers failed. Tried: {', '.join(sorted(tried))}")


def list_providers() -> dict[str, str]:
    return dict(PROVIDER_MODELS)
