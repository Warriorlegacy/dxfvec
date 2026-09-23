"""Tests for LLM pipeline JSON extraction — _extract_json and _scale_geometry."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

pytest.importorskip(
    "litellm",
    reason="litellm is an optional dependency (crew extra); these tests need it via dxfvec.pipeline -> providers",
)

from dxfvec.pipeline import _extract_json, _scale_geometry


class TestExtractJson:
    """Test the multiple-strategy JSON extraction from LLM responses."""

    def test_direct_parse(self):
        text = '{"outlines": [{"points": [[0,0],[1,0],[1,1]]}]}'
        result = _extract_json(text, "test_provider")
        assert result is not None
        assert "outlines" in result

    def test_json_in_markdown_block(self):
        text = 'Here is the result:\n```json\n{"outlines": [{"points": [[0,0]]}]}\n```'
        result = _extract_json(text, "test_provider")
        assert result is not None
        assert "outlines" in result

    def test_json_with_surrounding_text(self):
        text = 'I found the geometry: {"outlines": []} and that is all.'
        result = _extract_json(text, "test_provider")
        assert result is not None
        assert "outlines" in result

    def test_empty_input_raises(self):
        with pytest.raises(ValueError, match="empty response"):
            _extract_json("", "test_provider")
        with pytest.raises(ValueError, match="empty response"):
            _extract_json(None, "test_provider")

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="did not return valid JSON"):
            _extract_json("just some text with no json", "test_provider")

    def test_nested_json(self):
        text = 'Result: {"outlines": [{"points": [[0,0],[1,0]], "layer": "CUT"}], "holes": []}'
        result = _extract_json(text, "test_provider")
        assert result is not None
        assert len(result["outlines"]) == 1
        assert result["outlines"][0]["layer"] == "CUT"

    def test_trailing_commas(self):
        text = '{"outlines": [{"points": [[0,0]]}]}'
        result = _extract_json(text, "test_provider")
        assert result is not None
        assert "outlines" in result

    def test_json_with_extra_whitespace(self):
        text = '  \n  {"outlines": []}  \n  '
        result = _extract_json(text, "test_provider")
        assert result is not None

    def test_json_with_single_quotes_fails(self):
        text = "{'outlines': []}"
        with pytest.raises(ValueError):
            _extract_json(text, "test_provider")

    def test_json_with_newlines(self):
        text = '{\n  "outlines": [\n    {"points": [[0,0],[10,0],[10,10]]}\n  ]\n}'
        result = _extract_json(text, "test_provider")
        assert result is not None
        assert len(result["outlines"]) == 1

    def test_full_geometry_response(self):
        text = '''```json
{
  "outlines": [{"points": [[0,0],[100,0],[100,50],[0,50]], "closed": true}],
  "holes": [{"cx": 50.0, "cy": 25.0, "r": 10.0}],
  "bend_lines": [],
  "dimensions": [{"x": 50, "y": 60, "text": "100mm"}],
  "ambiguities": [],
  "confidence": "high"
}
```'''
        result = _extract_json(text, "test_provider")
        assert result is not None
        assert len(result["outlines"]) == 1
        assert len(result["holes"]) == 1
        assert result["confidence"] == "high"

    def test_provider_name_in_error(self):
        with pytest.raises(ValueError, match="my_custom_provider"):
            _extract_json("no json here", "my_custom_provider")


class TestScaleGeometry:
    """Test coordinate scaling in geometry dicts."""

    def test_scale_outlines(self):
        geo = {"outlines": [{"points": [[10, 20], [30, 40]]}]}
        scaled = _scale_geometry(geo, 2.0)
        assert scaled["outlines"][0]["points"] == [[20, 40], [60, 80]]

    def test_scale_holes(self):
        geo = {"holes": [{"cx": 50, "cy": 50, "r": 10}]}
        scaled = _scale_geometry(geo, 0.5)
        assert scaled["holes"][0]["cx"] == 25
        assert scaled["holes"][0]["cy"] == 25
        assert scaled["holes"][0]["r"] == 5

    def test_scale_bend_lines(self):
        geo = {"bend_lines": [{"points": [[0, 0], [100, 100]]}]}
        scaled = _scale_geometry(geo, 3.0)
        assert scaled["bend_lines"][0]["points"] == [[0, 0], [300, 300]]

    def test_scale_dimensions_position(self):
        geo = {"dimensions": [{"x": 10, "y": 20, "text": "100mm"}]}
        scaled = _scale_geometry(geo, 2.0)
        assert scaled["dimensions"][0]["x"] == 20
        assert scaled["dimensions"][0]["y"] == 40
        assert scaled["dimensions"][0]["text"] == "100mm"  # text untouched

    def test_scale_does_not_mutate_original(self):
        geo = {"outlines": [{"points": [[10, 20]]}]}
        _scale_geometry(geo, 5.0)
        assert geo["outlines"][0]["points"] == [[10, 20]]

    def test_scale_empty_geometry(self):
        scaled = _scale_geometry({}, 2.0)
        assert scaled == {}

    def test_scale_factor_one(self):
        geo = {"outlines": [{"points": [[5, 10]]}]}
        scaled = _scale_geometry(geo, 1.0)
        assert scaled["outlines"][0]["points"] == [[5, 10]]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
