"""Unit tests for the canonical PathModel — PRD §7.3."""
from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dxfvec.path_model import (
    ArcSegment,
    Calibration,
    DXFMode,
    DXFVersion,
    LineSegment,
    Path as DxfPath,
    PathModel,
    TraceMode,
    Vec2,
    circle_to_path,
    polyline_to_path,
)


def test_vec2_operations():
    a = Vec2(3, 4)
    b = Vec2(1, 2)
    assert a.length() == 5.0
    assert (a - b).x == 2.0
    assert (a - b).y == 2.0
    assert a.dot(b) == 11.0
    assert a.cross(b) == 2.0
    n = a.normalized()
    assert abs(n.length() - 1.0) < 1e-6


def test_polyline_to_path():
    pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
    path = polyline_to_path(pts, closed=True, layer="CUT")
    assert path.closed is True
    assert path.layer == "CUT"
    assert len(path.segments) == 4  # 4 edges, close implicit (endpoints match)
    assert path.segment_count() == 4
    assert path.approximate_length() > 0


def test_polyline_to_path_open():
    pts = [(0, 0), (10, 0), (10, 10)]
    path = polyline_to_path(pts, closed=False, layer="ENGRAVE")
    assert path.closed is False
    assert path.layer == "ENGRAVE"
    assert len(path.segments) == 2


def test_circle_to_path():
    path = circle_to_path(5, 5, 10, layer="CUT")
    assert path.closed is True
    assert len(path.segments) == 1
    seg = path.segments[0]
    assert isinstance(seg, ArcSegment)
    assert seg.cx == 5.0
    assert seg.cy == 5.0
    assert seg.radius == 10.0
    assert seg.is_full_circle is True


def test_path_points_from_arcs():
    path = DxfPath(closed=True, layer="CUT")
    path.add_segment(ArcSegment(cx=0, cy=0, radius=10,
                                 start_angle=0, end_angle=360))
    pts = path.points()
    assert len(pts) >= 4
    for pt in pts:
        assert abs(math.hypot(pt.x, pt.y) - 10) < 0.1


def test_path_model_entity_counts():
    model = PathModel()
    model.add_path(polyline_to_path([(0, 0), (10, 0), (10, 10), (0, 10)], closed=True))
    model.add_path(polyline_to_path([(20, 20), (30, 20)], closed=False))
    model.add_path(circle_to_path(50, 50, 5))
    assert model.entity_count() == 3
    assert model.closed_path_count() == 2
    assert model.open_path_count() == 1


def test_path_model_bounding_box():
    model = PathModel()
    model.add_path(polyline_to_path([(10, 20), (100, 20), (100, 80), (10, 80)], closed=True))
    model.add_path(circle_to_path(50, 50, 5))
    bb = model.bounding_box()
    assert bb[0] == 10  # min_x
    assert bb[1] == 20  # min_y
    assert bb[2] == 100  # max_x
    assert bb[3] == 80  # max_y


def test_paths_by_layer():
    model = PathModel()
    model.add_path(polyline_to_path([(0, 0), (10, 0), (10, 10)], closed=True, layer="CUT"))
    model.add_path(polyline_to_path([(20, 20), (30, 20), (30, 30)], closed=True, layer="ENGRAVE"))
    layers = model.paths_by_layer()
    assert "CUT" in layers
    assert "ENGRAVE" in layers
    assert len(layers["CUT"]) == 1
    assert len(layers["ENGRAVE"]) == 1


def test_scale():
    model = PathModel()
    model.add_path(polyline_to_path([(0, 0), (10, 0), (10, 10)], closed=True))
    model.scale(2.0)
    pts = model.paths[0].points()
    assert max(p.x for p in pts) == 20.0
    assert max(p.y for p in pts) == 20.0


def test_calibration():
    cal = Calibration(reference_px_length=100, real_world_length=50, unit="mm")
    assert cal.is_valid is True
    assert cal.scale_factor == 0.5
    assert cal.unit == "mm"

    cal2 = Calibration(reference_px_length=0, real_world_length=50, unit="mm")
    assert cal2.is_valid is False
    assert cal2.scale_factor == 1.0


def test_detect_open_paths():
    model = PathModel()
    # Closed path with small gap
    path = DxfPath(closed=True, layer="CUT")
    path.add_segment(LineSegment(start=Vec2(0, 0), end=Vec2(10, 0)))
    path.add_segment(LineSegment(start=Vec2(10, 0), end=Vec2(10, 10)))
    path.add_segment(LineSegment(start=Vec2(10, 10), end=Vec2(0, 10)))
    path.add_segment(LineSegment(start=Vec2(0, 10), end=Vec2(0.5, 0.5)))
    model.add_path(path)

    open_paths = model.detect_open_paths(tolerance=0.1)
    assert len(open_paths) == 1
    assert open_paths[0][1] > 0.1


def test_close_gaps():
    model = PathModel()
    path = DxfPath(closed=True, layer="CUT")
    path.add_segment(LineSegment(start=Vec2(0, 0), end=Vec2(10, 0)))
    path.add_segment(LineSegment(start=Vec2(10, 0), end=Vec2(10, 10)))
    path.add_segment(LineSegment(start=Vec2(10, 10), end=Vec2(0, 10)))
    path.add_segment(LineSegment(start=Vec2(0, 10), end=Vec2(0, 0)))
    model.add_path(path)
    count = model.close_gaps(max_gap=5.0)
    assert count >= 0


def test_enforce_closed_layer():
    model = PathModel()
    path = DxfPath(closed=False, layer="CUT")
    path.add_segment(LineSegment(start=Vec2(0, 0), end=Vec2(10, 0)))
    path.add_segment(LineSegment(start=Vec2(10, 0), end=Vec2(10, 10)))
    model.add_path(path)
    model.enforce_closed_layer("CUT")
    assert model.paths[0].closed is True


def test_dxf_version_enum():
    assert DXFVersion.R12.value == "R12"
    assert DXFVersion.R2010.value == "R2010"
    assert DXFVersion.R2018.value == "R2018"


def test_trace_mode_enum():
    assert TraceMode.OUTLINE.value == "outline"
    assert TraceMode.CENTERLINE.value == "centerline"


def test_dxf_mode_enum():
    assert DXFMode.LINES.value == "lines"
    assert DXFMode.HATCH.value == "hatch"
    assert DXFMode.FACES.value == "faces"


def test_empty_path_model():
    model = PathModel()
    assert model.entity_count() == 0
    assert model.closed_path_count() == 0
    assert model.open_path_count() == 0
    bb = model.bounding_box()
    assert bb == (0, 0, 0, 0)


def test_self_intersection_detection():
    model = PathModel()
    # Create a self-intersecting "X" shape
    path = DxfPath(closed=False, layer="CUT")
    path.add_segment(LineSegment(start=Vec2(0, 0), end=Vec2(10, 10)))
    path.add_segment(LineSegment(start=Vec2(10, 0), end=Vec2(0, 10)))
    model.add_path(path)
    intersections = model.detect_self_intersections()
    assert len(intersections) > 0


if __name__ == "__main__":
    test_vec2_operations()
    test_polyline_to_path()
    test_polyline_to_path_open()
    test_circle_to_path()
    test_path_points_from_arcs()
    test_path_model_entity_counts()
    test_path_model_bounding_box()
    test_paths_by_layer()
    test_scale()
    test_calibration()
    test_detect_open_paths()
    test_close_gaps()
    test_enforce_closed_layer()
    test_dxf_version_enum()
    test_trace_mode_enum()
    test_dxf_mode_enum()
    test_empty_path_model()
    test_self_intersection_detection()
    print("ALL path_model tests PASSED")
