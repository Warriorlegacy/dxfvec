"""Arc and circle detection for polyline paths — PRD §3.3 P0.

Converts polyline approximations of curves into true CAD entities:
  - ARC (partial circle arcs)
  - CIRCLE (closed circular paths)

Algorithm:
  1. Walk a polyline's segments in a sliding window.
  2. For each window, fit a circle via least-squares (Taubin or Kasa method).
  3. Measure max deviation from the fitted circle.
  4. If deviation <= tolerance, replace the polyline segment(s) with an
     ArcSegment.
  5. For a closed polyline where the full circle fit passes, replace the
     entire path with a CIRCLE entity (via circle_to_path).

This is critical for CNC/laser quality — true arcs produce dramatically
smoother toolpaths than polygon approximations.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from .path_model import (
    ArcSegment,
    LineSegment,
    Path,
    PathModel,
    Vec2,
    circle_to_path,
)


def detect_and_replace_arcs(
    model: PathModel,
    max_deviation: float = 0.5,
    min_arc_length: float = 10.0,
    min_points_for_arc: int = 4,
    sliding_window_size: int = 6,
    full_circle_tolerance: float = 0.3,
) -> int:
    """Walk all paths in a model and replace polyline approximations with
    ArcSegments where a circular fit passes the tolerance check.

    Args:
        model: PathModel to modify in-place.
        max_deviation: Max pixel/mm distance from fitted circle to accept.
        min_arc_length: Minimum arc chord length to attempt fitting.
        min_points_for_arc: Minimum number of points to attempt arc fit.
        sliding_window_size: Number of consecutive segments to examine.
        full_circle_tolerance: Max deviation to accept a full circle replacement.

    Returns:
        Number of arcs detected and replaced.
    """
    replaced_count = 0

    for path_idx, path in enumerate(model.paths):
        pts = path.points()
        if len(pts) < min_points_for_arc:
            continue

        # Check if entire path is a candidate for full circle
        if path.closed and len(pts) >= 8:
            cx, cy, r, dev = _fit_circle_taubin(pts)
            if dev <= full_circle_tolerance and r > 0:
                model.paths[path_idx] = circle_to_path(
                    cx=cx, cy=cy, radius=r, layer=path.layer,
                )
                replaced_count += 1
                continue

        # Sliding window arc detection
        new_segments: list = []
        i = 0
        while i < len(pts) - 1:
            best_end = i + 1
            best_cx = best_cy = best_r = 0.0
            best_dev = float("inf")

            for j in range(
                i + min_points_for_arc - 1,
                min(i + sliding_window_size + min_points_for_arc, len(pts))
            ):
                window = pts[i:j + 1]
                if len(window) < min_points_for_arc:
                    continue

                chord_len = (window[-1] - window[0]).length()
                if chord_len < min_arc_length:
                    continue

                cx, cy, r, dev = _fit_circle_taubin(window)

                if dev <= max_deviation and r > 0:
                    # Check the fit is actually an arc (not a straight line)
                    curvature = 1.0 / max(r, 1e-6)
                    if curvature > 0.01:
                        if dev < best_dev:
                            best_dev = dev
                            best_end = j
                            best_cx, best_cy, best_r = cx, cy, r

            if best_end > i + 1:
                # Replace window with arc
                start_angle = math.degrees(
                    math.atan2(pts[i].y - best_cy, pts[i].x - best_cx)
                )
                end_angle = math.degrees(
                    math.atan2(pts[best_end].y - best_cy, pts[best_end].x - best_cx)
                )
                if end_angle < start_angle:
                    end_angle += 360.0

                arc = ArcSegment(
                    cx=best_cx,
                    cy=best_cy,
                    radius=best_r,
                    start_angle=start_angle,
                    end_angle=end_angle,
                    is_counterclockwise=True,
                )
                new_segments.append(arc)
                i = best_end
                replaced_count += 1
            else:
                new_segments.append(
                    LineSegment(start=pts[i], end=pts[i + 1])
                )
                i += 1

        if len(new_segments) > 0:
            if isinstance(new_segments[-1], LineSegment) and path.closed:
                gap = (new_segments[-1].end - pts[0]).length()
                if gap > 1e-6:
                    new_segments.append(
                        LineSegment(start=new_segments[-1].end, end=pts[0])
                    )
            path.segments = new_segments

    return replaced_count


def _fit_circle_taubin(
    points: Sequence[Vec2 | tuple | list],
) -> tuple[float, float, float, float]:
    """Taubin least-squares circle fit with geometric fallback.

    Returns (cx, cy, radius, max_deviation).
    Falls back to geometric fit if SVD is numerically unstable.
    """
    pts = np.array([(p.x if isinstance(p, Vec2) else p[0],
                     p.y if isinstance(p, Vec2) else p[1])
                    for p in points], dtype=np.float64)

    if len(pts) < 3:
        return (0, 0, 0, float("inf"))

    x = pts[:, 0]
    y = pts[:, 1]

    centroid_x = np.mean(x)
    centroid_y = np.mean(y)

    Z = np.column_stack([
        x - centroid_x,
        y - centroid_y,
        x**2 - np.mean(x**2) + y**2 - np.mean(y**2),
    ])

    try:
        _, _, Vt = np.linalg.svd(Z, full_matrices=False)
        A = Vt[2, :]

        denom = 2.0 * A[2]
        if abs(denom) < 1e-12:
            return _fit_circle_geometric(points)

        cx = centroid_x - A[0] / denom
        cy = centroid_y - A[1] / denom
        radicand = A[0]**2 + A[1]**2 - 4.0 * A[2] * (np.mean(x**2 + y**2) - centroid_x**2 - centroid_y**2)
        if radicand < 0:
            return _fit_circle_geometric(points)
        r = math.sqrt(radicand) / abs(denom)

        if r <= 0 or math.isnan(r) or math.isinf(r):
            return _fit_circle_geometric(points)

        dists = np.sqrt((x - cx)**2 + (y - cy)**2)
        max_dev = float(np.max(np.abs(dists - r)))

        return (float(cx), float(cy), float(r), max_dev)
    except np.linalg.LinAlgError:
        return _fit_circle_geometric(points)


def _fit_circle_geometric(
    points: Sequence[Vec2 | tuple | list],
) -> tuple[float, float, float, float]:
    """Geometric circle fit using perpendicular bisector intersection.

    More numerically stable than algebraic methods for near-perfect circles.
    """
    pts = [Vec2(float(p[0]), float(p[1])) if not isinstance(p, Vec2) else p
           for p in points]
    n = len(pts)
    if n < 3:
        return (0, 0, 0, float("inf"))

    # Use three well-separated points to estimate center
    i1, i2, i3 = 0, n // 3, 2 * n // 3
    p1, p2, p3 = pts[i1], pts[i2], pts[i3]

    # Perpendicular bisectors of chords p1-p2 and p2-p3
    mid1 = Vec2((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)
    mid2 = Vec2((p2.x + p3.x) / 2, (p2.y + p3.y) / 2)
    d1 = Vec2(-(p2.y - p1.y), p2.x - p1.x)
    d2 = Vec2(-(p3.y - p2.y), p3.x - p2.x)

    cross = d1.cross(d2)
    if abs(cross) < 1e-12:
        # Points are collinear, use full least-squares
        cx = np.mean([p.x for p in pts])
        cy = np.mean([p.y for p in pts])
    else:
        t = (mid2 - mid1).cross(d2) / cross
        cx = mid1.x + d1.x * t
        cy = mid1.y + d1.y * t

    r = np.mean([math.hypot(p.x - cx, p.y - cy) for p in pts])
    if r <= 0 or math.isnan(r) or math.isinf(r):
        return (0, 0, 0, float("inf"))

    max_dev = float(np.max(np.abs(
        [math.hypot(p.x - cx, p.y - cy) - r for p in pts]
    )))
    return (float(cx), float(cy), float(r), max_dev)


def _fit_circle_kasa(points: Sequence) -> tuple[float, float, float, float]:
    """Kasa circle fit (fast, biased towards small circles).

    Useful as a quick check before the more expensive Taubin fit.
    """
    pts = np.array([(p.x if isinstance(p, Vec2) else p[0],
                     p.y if isinstance(p, Vec2) else p[1])
                    for p in points], dtype=np.float64)

    n = len(pts)
    if n < 3:
        return (0, 0, 0, float("inf"))

    x = pts[:, 0]
    y = pts[:, 1]

    A = np.column_stack([x, y, np.ones(n)])
    b = x**2 + y**2

    try:
        sol, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return (0, 0, 0, float("inf"))

    cx = sol[0] / 2.0
    cy = sol[1] / 2.0
    r = math.sqrt(sol[2] + cx**2 + cy**2)

    if r <= 0 or math.isnan(r) or math.isinf(r):
        return (0, 0, 0, float("inf"))

    dists = np.sqrt((x - cx)**2 + (y - cy)**2)
    max_dev = float(np.max(np.abs(dists - r)))

    return (float(cx), float(cy), float(r), max_dev)


def compute_curvature(points: Sequence, window: int = 3) -> list[float]:
    """Compute discrete curvature at each point of a polyline."""
    pts = list(points)
    curvatures: list[float] = []
    for i in range(len(pts)):
        prev = pts[max(0, i - window)]
        curr = pts[i]
        nxt = pts[min(len(pts) - 1, i + window)]

        v1 = (curr.x - prev.x, curr.y - prev.y)
        v2 = (nxt.x - curr.x, nxt.y - curr.y)

        cross = v1[0] * v2[1] - v1[1] * v2[0]
        d1 = math.hypot(*v1)
        d2 = math.hypot(*v2)

        if d1 * d2 > 1e-6:
            curvatures.append(abs(cross) / (d1 * d2))
        else:
            curvatures.append(0.0)
    return curvatures


def douglas_peucker(
    points: list[Vec2],
    epsilon: float,
    closed: bool = False,
) -> list[Vec2]:
    """Ramer-Douglas-Peucker polyline simplification.

    Args:
        points: Input polyline vertices.
        epsilon: Max deviation in real-world units (tolerance).
        closed: If True, treat as closed polygon.

    Returns:
        Simplified point list.
    """
    if len(points) <= 2:
        return points

    pts = list(points)

    def _perpendicular_distance(p: Vec2, a: Vec2, b: Vec2) -> float:
        ab = b - a
        ap = p - a
        t = ab.dot(ap) / max(ab.dot(ab), 1e-12)
        t = max(0, min(1, t))
        projection = a + ab * t
        return (p - projection).length()

    def _simplify_segment(segment: list[Vec2]) -> list[Vec2]:
        if len(segment) <= 2:
            return segment
        max_dist = 0.0
        max_idx = 0
        a, b = segment[0], segment[-1]
        for i in range(1, len(segment) - 1):
            d = _perpendicular_distance(segment[i], a, b)
            if d > max_dist:
                max_dist = d
                max_idx = i
        if max_dist > epsilon:
            left = _simplify_segment(segment[:max_idx + 1])
            right = _simplify_segment(segment[max_idx:])
            return left[:-1] + right
        else:
            return [segment[0], segment[-1]]

    if closed and len(pts) > 3:
        simplified = _simplify_segment(pts + [pts[0]])
        if simplified and (simplified[-1] - simplified[0]).length() < epsilon:
            simplified = simplified[:-1]
        return simplified
    else:
        return _simplify_segment(pts)
