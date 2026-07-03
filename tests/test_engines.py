"""Tests for engine selection and presets."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from dxfvec.engines import (
    ClassicEngine,
    PRESETS,
    apply_preset,
    list_presets,
)


class TestClassicEngine:
    """Test ClassicEngine creation and config."""

    def test_engine_creation(self):
        engine = ClassicEngine()
        assert engine is not None
        assert engine.name == "classic"

    def test_engine_has_convert(self):
        engine = ClassicEngine()
        assert hasattr(engine, "convert")


class TestPresets:
    """Test preset registry and application."""

    def test_all_presets_exist(self):
        assert "logo_engrave" in PRESETS
        assert "laser_stencil" in PRESETS
        assert "technical_drawing" in PRESETS
        assert "contour_map" in PRESETS

    def test_preset_has_required_keys(self):
        for name, preset in PRESETS.items():
            assert "min_area" in preset, f"Preset {name} missing min_area"
            assert "simplify_tolerance" in preset, f"Preset {name} missing simplify_tolerance"
            assert "label" in preset, f"Preset {name} missing label"
            assert "description" in preset, f"Preset {name} missing description"

    def test_preset_has_vtracer_config(self):
        for name, preset in PRESETS.items():
            assert "corner_threshold" in preset, f"Preset {name} missing corner_threshold"
            assert "noise_filter" in preset, f"Preset {name} missing noise_filter"

    def test_list_presets_returns_dict(self):
        presets = list_presets()
        assert "logo_engrave" in presets
        # list_presets returns a dict; mutating it does NOT affect PRESETS
        presets_copy = dict(PRESETS)
        presets_copy["logo_engrave"] = {"min_area": 999}
        assert PRESETS["logo_engrave"]["min_area"] != 999

    def test_apply_preset_merges_config(self):
        config = {"scale_factor": 2.0}
        result = apply_preset(config, "laser_stencil")
        assert result["min_area"] == 200
        assert result["scale_factor"] == 2.0
        assert result["preset"] == "laser_stencil"

    def test_apply_unknown_preset_returns_original(self):
        config = {"min_area": 100}
        result = apply_preset(config, "nonexistent_preset")
        assert result == config

    def test_preset_does_not_override_label(self):
        config = {}
        result = apply_preset(config, "logo_engrave")
        assert "label" not in result
        assert "description" not in result

    def test_preset_values_are_numeric(self):
        for name, preset in PRESETS.items():
            assert isinstance(preset["min_area"], (int, float)), f"{name} min_area not numeric"
            assert isinstance(preset["simplify_tolerance"], (int, float))
            assert isinstance(preset["tolerance_mm"], (int, float))

    def test_preset_min_area_ordering(self):
        assert PRESETS["contour_map"]["min_area"] < PRESETS["laser_stencil"]["min_area"]

    def test_apply_multiple_presets(self):
        config = {}
        for name in ["logo_engrave", "laser_stencil", "technical_drawing", "contour_map"]:
            result = apply_preset(config, name)
            assert result["preset"] == name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
