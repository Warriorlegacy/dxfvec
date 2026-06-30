# dxf-vectorizer

Raster engineering drawings → layered DXF (CUT / BEND / DIM layers).

## Quick start

```bash
# Install
pip install -e .

# Convert a drawing (auto-fallback if provider fails)
dxfvec convert my_drawing.png

# With real-world scale
dxfvec convert my_drawing.png --scale "3.2px=1mm"

# Force a specific provider
dxfvec convert my_drawing.png --provider mistral

# List all providers
dxfvec providers
```

## Setup

1. Copy `.env.example` to `.env` (or just set `GEMINI_API_KEY` in `.env`)
2. Get a free Gemini API key at https://aistudio.google.com/apikey
3. Run `dxfvec convert <your_drawing.png>`

## Supported providers

| Provider | Model | API key env var |
|----------|-------|-----------------|
| **google** (default) | gemini-2.5-flash | `GEMINI_API_KEY` |
| openrouter | anthropic/claude-sonnet-4 | `OPENROUTER_API_KEY` |
| groq | llama-3.3-70b-versatile | `GROQ_API_KEY` |
| mistral | mistral-large-latest | `MISTRAL_API_KEY` |
| openai | gpt-4o | `OPENAI_API_KEY` |
| cerebras | llama-3.3-70b | `CEREBRAS_API_KEY` |
| cohere | command-r-plus | `COHERE_API_KEY` |
| nvidia | llama-3.1-70b-instruct | `NVIDIA_API_KEY` |
| xai | grok-2 | `XAI_API_KEY` |
| ollama | llava | none (local) |
| azure | gpt-4o | `AZURE_API_KEY` + `AZURE_API_BASE` |
| anthropic | claude-opus-4-6 | `ANTHROPIC_API_KEY` |

## Automatic fallback

If the primary provider fails (rate limit, outage, missing key), `dxfvec` automatically tries the next provider in the chain:

```
google → openrouter → groq → mistral → openai → cerebras → cohere → nvidia → xai
```

This is silent by default. To see which provider was used, check `review.md` or run with verbose output.

## Output files

| File | Description |
|------|-------------|
| `drawing.dxf` | Vectorized DXF with CUT, BEND, DIM layers |
| `review.md` | Detection report (entity table, confidence, ambiguities) |
| `preprocessed.png` | The binarised image used for analysis |

## Scale calibration

Use `--scale` to convert pixel coordinates to real-world mm:

```bash
# "64 pixels = 20 mm" → 3.2 px/mm
dxfvec convert drawing.png --scale "64px=20mm"

# Direct ratio
dxfvec convert drawing.png --scale 3.2

# Other units
dxfvec convert drawing.png --scale "96px=1in"
dxfvec convert drawing.png --scale "100px=5cm"
```

Without `--scale`, the DXF uses pixel coordinates (useful for relative geometry).

---

## Future: CMA cloud deployment

CMA (Claude Managed Agents) configs are in `cma/` for future use.
Requires an `ANTHROPIC_API_KEY` — see `cma/` for details.
