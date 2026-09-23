"""Tests for vision provider system — model resolution and fallback."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

pytest.importorskip(
    "litellm",
    reason="litellm is an optional dependency (crew extra); these tests exercise litellm-backed providers",
)

from dxfvec.providers import (
    PROVIDER_MODELS,
    FALLBACK_CHAIN,
    resolve_model,
    list_providers,
    _build_messages,
)


class TestResolveModel:
    """Test model string resolution for providers."""

    def test_google_resolves(self):
        model = resolve_model("google")
        assert model == "gemini/gemini-2.5-flash"

    def test_openai_resolves(self):
        model = resolve_model("openai")
        assert model == "openai/gpt-4o"

    def test_anthropic_resolves(self):
        model = resolve_model("anthropic")
        assert model == "anthropic/claude-opus-4-6"

    def test_full_litellm_string_passthrough(self):
        model = resolve_model("openai/gpt-4o-mini")
        assert model == "openai/gpt-4o-mini"

    def test_unknown_provider_passthrough(self):
        model = resolve_model("custom_provider")
        assert model == "custom_provider"

    def test_case_insensitive(self):
        model = resolve_model("Google")
        assert model == "gemini/gemini-2.5-flash"

    def test_all_providers_resolve(self):
        for name, expected in PROVIDER_MODELS.items():
            model = resolve_model(name)
            assert model == expected, f"Provider {name} resolved to {model}"


class TestProviderModels:
    """Test the provider registry."""

    def test_provider_count(self):
        assert len(PROVIDER_MODELS) == 12

    def test_list_providers(self):
        providers = list_providers()
        assert "google" in providers
        assert "openai" in providers
        assert isinstance(providers, dict)

    def test_fallback_chain_no_duplicates(self):
        assert len(FALLBACK_CHAIN) == len(set(FALLBACK_CHAIN))

    def test_fallback_chain_excludes_ollama(self):
        assert "ollama" not in FALLBACK_CHAIN


class TestBuildMessages:
    """Test message payload construction."""

    def test_message_structure(self):
        messages = _build_messages("base64data", "image/png", "Describe this")
        assert len(messages) == 1
        msg = messages[0]
        assert msg["role"] == "user"
        assert len(msg["content"]) == 2
        assert msg["content"][0]["type"] == "image_url"
        assert "data:image/png;base64,base64data" in msg["content"][0]["image_url"]["url"]
        assert msg["content"][1]["type"] == "text"
        assert msg["content"][1]["text"] == "Describe this"

    def test_different_media_types(self):
        for ext, mt in [("jpg", "image/jpeg"), ("bmp", "image/bmp"), ("tiff", "image/tiff")]:
            messages = _build_messages("x", mt, "prompt")
            assert mt in messages[0]["content"][0]["image_url"]["url"]


class TestVisionCall:
    """Test the vision_call function (mocked)."""

    @patch("dxfvec.providers.litellm.completion")
    def test_primary_success(self, mock_completion):
        from dxfvec.providers import vision_call
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "success"
        mock_completion.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "test.png"
            img_path.write_bytes(b"\x89PNG\r\n")
            result = vision_call(img_path, "Describe", provider="google", fallback=False)
            assert result == "success"
            assert mock_completion.call_count == 1

    @patch("dxfvec.providers.litellm.completion")
    def test_fallback_on_failure(self, mock_completion):
        from dxfvec.providers import vision_call
        mock_completion.side_effect = [
            Exception("Rate limited"),
            MagicMock(choices=[MagicMock(message=MagicMock(content="fallback ok"))]),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "test.png"
            img_path.write_bytes(b"\x89PNG\r\n")
            result = vision_call(img_path, "Describe", provider="google", fallback=True)
            assert result == "fallback ok"

    def test_file_not_found(self):
        from dxfvec.providers import vision_call
        with pytest.raises(FileNotFoundError):
            vision_call(Path("/nonexistent/image.png"), "Describe", fallback=False)

    @patch("dxfvec.providers.litellm.completion")
    def test_all_providers_fail_raises(self, mock_completion):
        from dxfvec.providers import vision_call
        mock_completion.side_effect = Exception("fail")

        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "test.png"
            img_path.write_bytes(b"\x89PNG\r\n")
            with pytest.raises(RuntimeError, match="All providers failed"):
                vision_call(img_path, "Describe", provider="google", fallback=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
