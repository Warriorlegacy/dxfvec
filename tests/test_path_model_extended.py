"""Extended tests for path model — Vec2, Calibration, PathModel edge cases."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from dxfvec.path_model import (
    ArcSegment,
    BezierSegment,
    Calibration,
    LineSegment,
    Path,
    PathModel,
    Vec2,
    circle_to_path,
    polyline_to_path,
)


class TestVec2Extended:
    """Extended Vec2 tests beyond the basics."""

    def test_hash_consistency(self):
        """Equal Vec2 objects must have equal hashes."""
        a = Vec2(1.000000000001, 2.0)
        b = Vec2(1.000000000002, 2.0)
        assert a == b
        assert hash(a) == hash(b)

    def test_vec2_in_set(self):
        s = {Vec2(1.0, 2.0), Vec2(1.0, 2.0)}
        assert len(s) == 1

    def test_vec2_distance(self):
        a = Vec2(0, 0)
        b = Vec2(3, 4)
        assert (a - b).length() == 5.0

    def test_vec2_add(self):
        a = Vec2(1, 2)
        b = Vec2(3, 4)
        c = a + b
        assert c.x == 4
        assert c.y == 6

    def test_vec2_mul(self):
        a = Vec2(2, 3)
        b = a * 3
        assert b.x == 6
        assert b.y == 9

    def test_vec2_iter(self):
        a = Vec2(1.0, 2.0)
        coords = list(a)
        assert coords == [1.0, 2.0]

    def test_vec2_to_tuple(self):
        a = Vec2(3.0, 4.0)
        assert a.to_tuple() == (3.0, 4.0)

    def test_vec2_eq_different_type(self):
        a = Vec2(1, 2)
        assert a != "not a Vec2"

    def test_vec2_normalized_zero(self):
        a = Vec2(0, 0)
        n = a.normalized()
        assert n.x == 0
        assert n.y == 0

    def test_vec2_normalized_unit(self):
        a = Vec2(3, 4)
        n = a.normalized()
        assert abs(n.length() - 1.0) < 1e-6

    def test_vec2_dot_product(self):
        a = Vec2(1, 0)
        b = Vec2(0, 1)
        assert a.dot(b) == 0

    def test_vec2_cross_product(self):
        a = Vec2(1, 0)
        b = Vec2(0, 1)
        assert a.cross(b) == 1.0

    def test_vec2_negative(self):
        a = Vec2(3, -4)
        b = a * -1
        assert b.x == -3
        assert b.y == 4

    def test_vec2_mul_float(self):
        a = Vec2(2, 3)
        b = a * 0.5
        assert b.x == 1.0
        assert b.y == 1.5


class TestCalibrationExtended:
    """Extended calibration tests."""

    def test_valid_calibration(self):
        cal = Calibration(reference_px_length=100, real_world_length=25.4, unit="mm")
        assert cal.is_valid
        assert abs(cal.scale_factor - 0.254) < 0.001

    def test_zero_reference_raises(self):
        cal = Calibration(reference_px_length=0, real_world_length=100, unit="mm")
        assert not cal.is_valid
        with pytest.raises(ValueError):
            _ = cal.scale_factor

    def test_negative_reference_raises(self):
        cal = Calibration(reference_px_length=-10, real_world_length=100, unit="mm")
        with pytest.raises(ValueError):
            _ = cal.scale_factor

    def test_valid_units(self):
        for unit in ["mm", "cm", "in", "px"]:
            cal = Calibration(reference_px_length=100, real_world_length=50, unit=unit)
            assert cal.is_valid, f"Unit {unit} should be valid"

    def test_invalid_unit(self):
        cal = Calibration(reference_px_length=100, real_world_length=50, unit="lightyears")
        assert not cal.is_valid

    def test_scale_factor_calculation(self):
        cal = Calibration(reference_px_length=200, real_world_length=100, unit="mm")
        assert cal.scale_factor == 0.5

    def test_calibration_defaults(self):
        cal = Calibration(reference_px_length=50, real_world_length=50)
        assert cal.unit == "mm"


class TestSegmentTypes:
    """Test different segment types."""

    def test_line_segment_length(self):
        seg = LineSegment(start=Vec2(0, 0), end=Vec2(3, 4))
        assert seg.length() == 5.0

    def test_arc_segment_full_circle(self):
        seg = ArcSegment(cx=0, cy=0, radius=5, start_angle=0, end_angle=360)
        assert seg.is_full_circle

    def test_arc_segment_not_full_circle(self):
        seg = ArcSegment(cx=0, cy=0, radius=5, start_angle=0, end_angle=180)
        assert not seg.is_full_circle

    def test_bezier_segment(self):
        seg = BezierSegment(
            p0=Vec2(0, 0), p1=Vec2(10, 0),
            p2=Vec2(10, 10), p3=Vec2(0, 10),
        )
        path = Path(closed=False)
        path.add_segment(seg)
        pts = path.points()
        assert len(pts) == 2  # p0 and p3


class TestPathModelExtended:
    """Extended PathModel tests."""

    def test_empty_pathmodel(self):
        model = PathModel()
        assert model.entity_count() == 0
        assert len(model.paths) == 0

    def test_bounding_box(self):
        model = PathModel()
        model.add_path(polyline_to_path([(0, 0), (10, 0), (10, 10), (0, 10)], closed=True))
        bb = model.bounding_box()
        assert bb[0] == 0
        assert bb[1] == 0
        assert bb[2] == 10
        assert bb[3] == 10

    def test_bounding_box_empty(self):
        model = PathModel()
        assert model.bounding_box() == (0, 0, 0, 0)

    def test_enforce_closed_layer_non_matching(self):
        model = PathModel()
        path = Path(closed=False, layer="ENGRAVE")
        path.add_segment(LineSegment(start=Vec2(0, 0), end=Vec2(10, 0)))
        model.add_path(path)
        model.enforce_closed_layer("CUT")
        assert model.paths[0].closed is False

    def test_paths_by_layer_multiple(self):
        model = PathModel()
        model.add_path(polyline_to_path([(0, 0), (1, 0)], closed=True, layer="CUT"))
        model.add_path(polyline_to_path([(0, 0), (1, 0)], closed=True, layer="CUT"))
        model.add_path(polyline_to_path([(0, 0), (1, 0)], closed=True, layer="ENGRAVE"))
        layers = model.paths_by_layer()
        assert len(layers["CUT"]) == 2
        assert len(layers["ENGRAVE"]) == 1

    def test_scale_with_arcs(self):
        model = PathModel()
        model.add_path(circle_to_path(50, 50, 10, layer="CUT"))
        model.scale(2.0)
        path = model.paths[0]
        seg = path.segments[0]
        assert isinstance(seg, ArcSegment)
        assert seg.cx == 100
        assert seg.cy == 100
        assert seg.radius == 20

    def test_scale_with_bezier(self):
        model = PathModel()
        path = Path(closed=False, layer="CUT")
        path.add_segment(BezierSegment(
            p0=Vec2(0, 0), p1=Vec2(10, 0),
            p2=Vec2(10, 10), p3=Vec2(0, 10),
        ))
        model.add_path(path)
        model.scale(3.0)
        seg = model.paths[0].segments[0]
        assert seg.p0.x == 0
        assert seg.p3.y == 30

    def test_close_gaps_large_gap_ignored(self):
        model = PathModel()
        path = Path(closed=True, layer="CUT")
        path.add_segment(LineSegment(start=Vec2(0, 0), end=Vec2(10, 0)))
        path.add_segment(LineSegment(start=Vec2(10, 0), end=Vec2(0, 100)))
        model.add_path(path)
        count = model.close_gaps(max_gap=5.0)
        assert count == 0

    def test_open_path_count(self):
        model = PathModel()
        model.add_path(polyline_to_path([(0, 0), (1, 0)], closed=True))
        model.add_path(polyline_to_path([(0, 0), (1, 0)], closed=False))
        assert model.closed_path_count() == 1
        assert model.open_path_count() == 1

    def test_detect_open_paths_gap(self):
        model = PathModel()
        path = Path(closed=True, layer="CUT")
        path.add_segment(LineSegment(start=Vec2(0, 0), end=Vec2(10, 0)))
        path.add_segment(LineSegment(start=Vec2(10, 0), end=Vec2(10, 10)))
        path.add_segment(LineSegment(start=Vec2(10, 10), end=Vec2(0, 10)))
        path.add_segment(LineSegment(start=Vec2(0, 10), end=Vec2(0.5, 0.5)))
        model.add_path(path)
        open_paths = model.detect_open_paths(tolerance=0.1)
        assert len(open_paths) == 1


class TestLayerNames:
    """Test layer name constants."""

    def test_layer_colors(self):
        from dxfvec.path_model import LAYER_COLORS
        assert LAYER_COLORS["CUT"] == 1
        assert LAYER_COLORS["ENGRAVE"] == 5
        assert LAYER_COLORS["BEND"] == 5
        assert LAYER_COLORS["DIM"] == 3
        assert LAYER_COLORS["SCRAP"] == 8

    def test_layer_linetypes(self):
        from dxfvec.path_model import LAYER_LINETYPES
        assert LAYER_LINETYPES["BEND"] == "DASHED"
        assert LAYER_LINETYPES["CUT"] == "CONTINUOUS"

    def test_layer_name_enum(self):
        from dxfvec.path_model import LayerName
        assert LayerName.CUT.value == "CUT"
        assert LayerName.SCRAP.value == "SCRAP"


class TestHelperFunctions:
    """Test polyline_to_path and circle_to_path edge cases."""

    def test_polyline_single_point(self):
        path = polyline_to_path([(5, 5)], closed=False, layer="CUT")
        assert path.closed is False
        assert len(path.segments) == 0

    def test_polyline_two_points_open(self):
        path = polyline_to_path([(0, 0), (10, 10)], closed=False)
        assert len(path.segments) == 1

    def test_polyline_vec2_input(self):
        path = polyline_to_path([Vec2(0, 0), Vec2(10, 0), Vec2(10, 10)], closed=True)
        assert path.closed is True

    def test_polyline_consecutive_duplicates_removed(self):
        path = polyline_to_path([(0, 0), (0, 0), (10, 0), (10, 0)], closed=False)
        assert len(path.segments) == 1

    def test_circle_to_path_custom_layer(self):
        path = circle_to_path(5, 5, 10, layer="ENGRAVE")
        assert path.layer == "ENGRAVE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
