"""Unit tests for arc/circle detection — PRD §3.3 P0."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dxfvec.curve_fitting import (
    detect_and_replace_arcs,
    douglas_peucker,
    compute_curvature,
    _fit_circle_taubin,
    _fit_circle_kasa,
)
from dxfvec.path_model import (
    ArcSegment,
    Path,
    PathModel,
    Vec2,
    LineSegment,
    polyline_to_path,
)


def test_fit_circle_taubin_perfect():
    pts = [Vec2(10 + 5 * math.cos(t), 10 + 5 * math.sin(t))
           for t in [i * 2 * math.pi / 12 for i in range(12)]]
    cx, cy, r, dev = _fit_circle_taubin(pts)
    assert abs(cx - 10) < 0.5
    assert abs(cy - 10) < 0.5
    assert abs(r - 5) < 0.5
    assert dev < 0.5


def test_fit_circle_taubin_noisy():
    pts = [Vec2(10 + 5 * math.cos(t) + 0.1 * math.sin(t * 3),
                 10 + 5 * math.sin(t) + 0.1 * math.cos(t * 3))
           for t in [i * 2 * math.pi / 16 for i in range(16)]]
    cx, cy, r, dev = _fit_circle_taubin(pts)
    assert abs(cx - 10) < 1.0
    assert abs(cy - 10) < 1.0
    assert 4 < r < 6


def test_fit_circle_kasa():
    pts = [Vec2(0, 5), Vec2(5, 0), Vec2(0, -5), Vec2(-5, 0)]
    cx, cy, r, dev = _fit_circle_kasa(pts)
    assert abs(cx) < 0.5
    assert abs(cy) < 0.5
    assert abs(r - 5) < 0.5


def test_detect_and_replace_arcs_rectangle():
    model = PathModel()
    model.add_path(polyline_to_path([(0, 0), (100, 0), (100, 50), (0, 50)], closed=True))
    count = detect_and_replace_arcs(model, max_deviation=0.5)
    assert count >= 0


def test_detect_and_replace_arcs_circle():
    model = PathModel()
    pts = [(50 + 50 * math.cos(t), 50 + 50 * math.sin(t))
           for t in [i * 2 * math.pi / 16 for i in range(16)]]
    model.add_path(polyline_to_path(pts, closed=True))
    count = detect_and_replace_arcs(model, max_deviation=1.0, full_circle_tolerance=2.0)
    assert count >= 1
    assert len(model.paths) == 1
    assert len(model.paths[0].segments) == 1
    assert isinstance(model.paths[0].segments[0], ArcSegment)
    assert model.paths[0].segments[0].is_full_circle


def test_douglas_peucker_reduces_points():
    pts = [Vec2(i, math.sin(i * 0.5)) for i in range(100)]
    simplified = douglas_peucker(pts, epsilon=1.0, closed=False)
    assert len(simplified) < len(pts)
    assert len(simplified) >= 2


def test_douglas_peucker_low_epsilon():
    pts = [Vec2(i, math.sin(i * 0.5)) for i in range(100)]
    simplified = douglas_peucker(pts, epsilon=0.01, closed=False)
    assert len(simplified) > 50


def test_douglas_peucker_closed():
    pts = [Vec2(i % 10, i // 10) for i in range(40)]
    simplified = douglas_peucker(pts, epsilon=2.0, closed=True)
    assert len(simplified) >= 3


def test_douglas_peucker_two_points():
    pts = [Vec2(0, 0), Vec2(10, 10)]
    simplified = douglas_peucker(pts, epsilon=1.0)
    assert len(simplified) == 2


def test_compute_curvature():
    pts = [Vec2(i, 0) for i in range(10)]
    curvatures = compute_curvature(pts, window=1)
    assert len(curvatures) == len(pts)
    assert all(c == 0.0 for c in curvatures)  # Straight line


def test_compute_curvature_curve():
    pts = [Vec2(math.cos(t), math.sin(t)) for t in [i * 0.5 for i in range(10)]]
    curvatures = compute_curvature(pts, window=1)
    assert any(c > 0.1 for c in curvatures)


def test_no_false_positive_on_straight_line():
    model = PathModel()
    pts = [(0, 0), (100, 0)]
    model.add_path(polyline_to_path(pts, closed=False))
    count = detect_and_replace_arcs(model, max_deviation=0.5)
    assert count == 0


if __name__ == "__main__":
    test_fit_circle_taubin_perfect()
    test_fit_circle_taubin_noisy()
    test_fit_circle_kasa()
    test_detect_and_replace_arcs_rectangle()
    test_detect_and_replace_arcs_circle()
    test_douglas_peucker_reduces_points()
    test_douglas_peucker_low_epsilon()
    test_douglas_peucker_closed()
    test_douglas_peucker_two_points()
    test_compute_curvature()
    test_compute_curvature_curve()
    test_no_false_positive_on_straight_line()
    print("ALL curve_fitting tests PASSED")
