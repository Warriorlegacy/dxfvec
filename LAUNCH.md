# dxfvec — LLM Vision Pipeline Quickstart

Raster engineering drawings → layered DXF (CUT / BEND / DIM layers) via vision LLM.

## Quick start

```bash
# Install with LLM dependencies
pip install -r requirements.txt && pip install -e ".[crew]"

# Convert a drawing (auto-fallback if provider fails)
dxfvec convert my_drawing.png --provider google

# With real-world scale
dxfvec convert my_drawing.png --provider google --scale "64px=20mm"

# Force a specific provider
dxfvec convert my_drawing.png --provider mistral

# List all providers
dxfvec providers
```

## Setup

1. The repo ships with `.env` containing keys for the full fallback chain. Alternatively, set `GEMINI_API_KEY` in your environment.
2. Get a free Gemini API key at https://aistudio.google.com/apikey
3. Run `dxfvec convert my_drawing.png --provider google`

## Supported providers

| Provider | Model | API key env var |
|----------|-------|-----------------|
| **google** (default) | gemini/gemini-2.5-flash | `GEMINI_API_KEY` |
| openrouter | openrouter/anthropic/claude-sonnet-4 | `OPENROUTER_API_KEY` |
| groq | groq/llama-3.3-70b-versatile | `GROQ_API_KEY` |
| mistral | mistral/mistral-large-latest | `MISTRAL_API_KEY` |
| openai | openai/gpt-4o | `OPENAI_API_KEY` |
| cerebras | cerebras/llama-3.3-70b | `CEREBRAS_API_KEY` |
| cohere | cohere/command-r-plus | `COHERE_API_KEY` |
| nvidia | nim/meta/llama-3.1-70b-instruct | `NVIDIA_API_KEY` |
| xai | xai/grok-2 | `XAI_API_KEY` |
| ollama | ollama/llava | none (local) |
| azure | azure/gpt-4o | `AZURE_API_KEY` + `AZURE_API_BASE` |
| anthropic | anthropic/claude-opus-4-6 | `ANTHROPIC_API_KEY` |

Any full LiteLLM model string also works, e.g. `--provider "openai/gpt-4o"`.

## Automatic fallback

If the primary provider fails (rate limit, outage, missing key), the pipeline automatically tries the next provider in the chain:

```
google → openrouter → groq → mistral → openai → cerebras → cohere → nvidia → xai
```

To see which provider was used, check `output/review.md` or run with `--debug`.

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
dxfvec convert drawing.png --provider google --scale "64px=20mm"

# Direct ratio
dxfvec convert drawing.png --provider google --scale 3.2

# Other units
dxfvec convert drawing.png --provider google --scale "96px=1in"
dxfvec convert drawing.png --provider google --scale "100px=5cm"
```

Without `--scale`, the DXF uses pixel coordinates (useful for relative geometry).

## Multi-agent CrewAI pipeline

For higher quality on complex drawings, use the three-agent CrewAI pipeline:

```bash
dxfvec convert my_drawing.png --provider google --crew
```
