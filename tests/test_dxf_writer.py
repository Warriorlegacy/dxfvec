"""Unit tests for the industry-grade DXF writer — PRD §3.4 P0."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import ezdxf

from dxfvec.path_model import (
    Calibration,
    DXFVersion,
    PathModel,
    polyline_to_path,
    circle_to_path,
    Path as DxfPath,
    ArcSegment,
    Vec2,
)
from dxfvec.dxf_writer import write_dxf, write_svg, LAYER_COLORS


def test_write_dxf_basic():
    model = PathModel()
    model.add_path(polyline_to_path([(0, 0), (100, 0), (100, 50), (0, 50)], closed=True, layer="CUT"))
    model.add_path(circle_to_path(50, 25, 10, layer="CUT"))

    with tempfile.TemporaryDirectory() as tmp:
        dxf_path = Path(tmp) / "test.dxf"
        result = write_dxf(model, dxf_path)
        assert result.exists()
        doc = ezdxf.readfile(str(result))
        msp = doc.modelspace()
        entities = list(msp)
        assert len(entities) >= 2


def test_write_dxf_versions():
    model = PathModel()
    model.add_path(polyline_to_path([(0, 0), (10, 0), (10, 10)], closed=True))

    with tempfile.TemporaryDirectory() as tmp:
        for version in [DXFVersion.R12, DXFVersion.R2010, DXFVersion.R2018]:
            dxf_path = Path(tmp) / f"test_{version.value}.dxf"
            write_dxf(model, dxf_path, dxf_version=version)
            doc = ezdxf.readfile(str(dxf_path))
            assert doc.dxfversion is not None


def test_write_dxf_with_units():
    model = PathModel()
    model.calibration = Calibration(reference_px_length=100, real_world_length=50, unit="in")
    model.add_path(polyline_to_path([(0, 0), (100, 0), (100, 50)], closed=True))

    with tempfile.TemporaryDirectory() as tmp:
        dxf_path = Path(tmp) / "test_units.dxf"
        write_dxf(model, dxf_path, units="in")
        doc = ezdxf.readfile(str(dxf_path))
        assert doc.header["$INSUNITS"] == 1


def test_write_dxf_with_calibration_mm():
    model = PathModel()
    model.calibration = Calibration(reference_px_length=100, real_world_length=50, unit="mm")
    model.add_path(polyline_to_path([(0, 0), (100, 0), (100, 50)], closed=True))

    with tempfile.TemporaryDirectory() as tmp:
        dxf_path = Path(tmp) / "test_cal.dxf"
        write_dxf(model, dxf_path)
        doc = ezdxf.readfile(str(dxf_path))
        assert doc.header["$INSUNITS"] == 4


def test_write_dxf_enforce_closed():
    model = PathModel()
    # Add an open path on CUT layer
    path = polyline_to_path([(0, 0), (10, 0), (10, 10)], closed=False, layer="CUT")
    model.add_path(path)

    with tempfile.TemporaryDirectory() as tmp:
        dxf_path = Path(tmp) / "test_enforce.dxf"
        write_dxf(model, dxf_path, enforce_closed_cut=True)
        doc = ezdxf.readfile(str(dxf_path))
        assert doc is not None


def test_write_dxf_arc_entity():
    model = PathModel()
    path = DxfPath(closed=False, layer="CUT")
    path.add_segment(ArcSegment(cx=0, cy=0, radius=10,
                                 start_angle=0, end_angle=180))
    model.add_path(path)

    with tempfile.TemporaryDirectory() as tmp:
        dxf_path = Path(tmp) / "test_arc.dxf"
        write_dxf(model, dxf_path)
        doc = ezdxf.readfile(str(dxf_path))
        entities = list(doc.modelspace())
        assert len(entities) >= 1


def test_write_dxf_full_circle_entity():
    model = PathModel()
    model.add_path(circle_to_path(5, 5, 10, layer="CUT"))

    with tempfile.TemporaryDirectory() as tmp:
        dxf_path = Path(tmp) / "test_circle.dxf"
        write_dxf(model, dxf_path)
        doc = ezdxf.readfile(str(dxf_path))
        entities = list(doc.modelspace())
        assert len(entities) >= 1


def test_write_svg():
    model = PathModel()
    model.add_path(polyline_to_path([(0, 0), (100, 0), (100, 50), (0, 50)], closed=True))
    model.add_path(circle_to_path(50, 25, 10))

    with tempfile.TemporaryDirectory() as tmp:
        svg_path = Path(tmp) / "test.svg"
        write_svg(model, svg_path)
        assert svg_path.exists()
        content = svg_path.read_text()
        assert "<svg" in content
        assert "path" in content


def test_layers_consistency():
    assert "CUT" in LAYER_COLORS
    assert "ENGRAVE" in LAYER_COLORS
    assert "BEND" in LAYER_COLORS
    assert "DIM" in LAYER_COLORS
    assert LAYER_COLORS["CUT"] == 1
    assert LAYER_COLORS["ENGRAVE"] == 5


def test_dxf_audit_after_write():
    model = PathModel()
    model.add_path(polyline_to_path([(0, 0), (100, 0), (100, 100), (0, 100)], closed=True, layer="CUT"))

    with tempfile.TemporaryDirectory() as tmp:
        dxf_path = Path(tmp) / "audit_test.dxf"
        write_dxf(model, dxf_path)
        doc = ezdxf.readfile(str(dxf_path))
        auditor = doc.audit()
        critical = [e for e in auditor.errors if hasattr(e, 'severity') and e.severity >= 50]
        assert len(critical) == 0


if __name__ == "__main__":
    test_write_dxf_basic()
    test_write_dxf_versions()
    test_write_dxf_with_units()
    test_write_dxf_with_calibration_mm()
    test_write_dxf_enforce_closed()
    test_write_dxf_arc_entity()
    test_write_dxf_full_circle_entity()
    test_write_svg()
    test_layers_consistency()
    test_dxf_audit_after_write()
    print("ALL dxf_writer tests PASSED")
