"""Canonical intermediate geometry representation for dxfvec.

All vectorization engines (Classic, VTracer, Cloud BYOK) produce this same
model, and all exporters (DXF, SVG, PDF) consume it. This is the single source
of truth — PRD §7.3.

Design:
  - Segments are typed (Line, Arc, Bezier) so exporters can emit native
    CAD entities (ARC, CIRCLE, LWPOLYLINE with bulges) rather than only
    polyline approximations.
  - Every path carries metadata (layer, closed, color) consistent with
    the layer-naming convention in PRD §5.4.
  - Validation methods (gap detection, self-intersection, bounding-box)
    ship with the model itself so QA is never blind.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class TraceMode(Enum):
    OUTLINE = "outline"
    CENTERLINE = "centerline"


class DXFMode(Enum):
    LINES = "lines"
    HATCH = "hatch"
    FACES = "faces"


class DXFVersion(Enum):
    R12 = "R12"
    R2010 = "R2010"
    R2018 = "R2018"


class LayerName(Enum):
    CUT = "CUT"
    ENGRAVE = "ENGRAVE"
    BEND = "BEND"
    DIM = "DIM"
    SCRAP = "SCRAP"


LAYER_COLORS: dict[str, int] = {
    "CUT": 1,
    "ENGRAVE": 5,
    "BEND": 5,
    "DIM": 7,
    "SCRAP": 8,
}

LAYER_LINETYPES: dict[str, str] = {
    "CUT": "CONTINUOUS",
    "ENGRAVE": "CONTINUOUS",
    "BEND": "DASHED",
    "DIM": "CONTINUOUS",
    "SCRAP": "CONTINUOUS",
}


@dataclass
class Vec2:
    x: float
    y: float

    def __iter__(self):
        yield self.x
        yield self.y

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vec2):
            return NotImplemented
        return abs(self.x - other.x) < 1e-12 and abs(self.y - other.y) < 1e-12

    def __hash__(self) -> int:
        return hash((round(self.x, 6), round(self.y, 6)))

    def __sub__(self, other: Vec2) -> Vec2:
        return Vec2(self.x - other.x, self.y - other.y)

    def __add__(self, other: Vec2) -> Vec2:
        return Vec2(self.x + other.x, self.y + other.y)

    def __mul__(self, s: float) -> Vec2:
        return Vec2(self.x * s, self.y * s)

    def dot(self, other: Vec2) -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: Vec2) -> float:
        return self.x * other.y - self.y * other.x

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> Vec2:
        L = self.length()
        if L < 1e-12:
            return Vec2(0, 0)
        return Vec2(self.x / L, self.y / L)

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class Segment:
    """Base segment — typed so exporters can emit native CAD entities."""


@dataclass
class LineSegment(Segment):
    start: Vec2
    end: Vec2

    def length(self) -> float:
        return (self.end - self.start).length()


@dataclass
class ArcSegment(Segment):
    """A circular arc. For a full circle, start_angle == end_angle or
    the arc spans 360°."""

    cx: float
    cy: float
    radius: float
    start_angle: float
    end_angle: float
    is_counterclockwise: bool = True

    @property
    def is_full_circle(self) -> bool:
        sweep = abs(self.end_angle - self.start_angle)
        return abs(sweep - 360.0) < 0.1 or abs(sweep) < 0.1


@dataclass
class BezierSegment(Segment):
    """Cubic Bezier curve."""
    p0: Vec2
    p1: Vec2
    p2: Vec2
    p3: Vec2


@dataclass
class Path:
    """A single vector path — the atomic unit of geometry.

    A path may consist of multiple segments of mixed types. For typical
    traced output most paths will contain a single polyline (many consecutive
    LineSegments), but after curve detection some LineSegments may be replaced
    by ArcSegments or BezierSegments.
    """
    segments: list[Segment] = field(default_factory=list)
    closed: bool = False
    layer: str = "CUT"
    color: int = 1

    def add_segment(self, seg: Segment) -> None:
        self.segments.append(seg)

    def points(self) -> list[Vec2]:
        pts: list[Vec2] = []
        for seg in self.segments:
            if isinstance(seg, LineSegment):
                if not pts or pts[-1] != seg.start:
                    pts.append(seg.start)
                pts.append(seg.end)
            elif isinstance(seg, BezierSegment):
                if not pts or pts[-1] != seg.p0:
                    pts.append(seg.p0)
                pts.append(seg.p3)
            elif isinstance(seg, ArcSegment):
                pt_count = max(6, int(abs(seg.end_angle - seg.start_angle) / 3))
                for i in range(pt_count):
                    frac = i / max(pt_count - 1, 1)
                    theta = math.radians(
                        seg.start_angle + frac * (seg.end_angle - seg.start_angle)
                    )
                    pt = Vec2(
                        seg.cx + seg.radius * math.cos(theta),
                        seg.cy + seg.radius * math.sin(theta),
                    )
                    if not pts or pts[-1] != pt:
                        pts.append(pt)
        return pts

    def segment_count(self) -> int:
        return len(self.segments)

    def approximate_length(self) -> float:
        total = 0.0
        for seg in self.segments:
            if isinstance(seg, LineSegment):
                total += seg.length()
            elif isinstance(seg, ArcSegment):
                sweep = abs(seg.end_angle - seg.start_angle)
                total += math.radians(sweep) * seg.radius
            elif isinstance(seg, BezierSegment):
                chord = (seg.p3 - seg.p0).length()
                total += chord
        return total


@dataclass
class Calibration:
    """Pixel-to-real-world scale calibration. PRD §5.1."""
    reference_px_length: float
    real_world_length: float
    unit: str = "mm"

    @property
    def scale_factor(self) -> float:
        if self.reference_px_length <= 0:
            return 1.0
        return self.real_world_length / self.reference_px_length

    @property
    def is_valid(self) -> bool:
        return (
            self.reference_px_length > 0
            and self.real_world_length > 0
            and self.unit in ("mm", "cm", "in", "px")
        )


@dataclass
class PathModel:
    """The canonical intermediate geometry model. PRD §7.3.

    All engines produce this; all exporters consume this. This is the
    single source of truth so SVG, DXF, and PDF outputs are guaranteed
    consistent.
    """
    paths: list[Path] = field(default_factory=list)
    calibration: Calibration | None = None
    trace_mode: TraceMode = TraceMode.OUTLINE
    dxf_mode: DXFMode = DXFMode.LINES
    dxf_version: DXFVersion = DXFVersion.R2010
    source_image: str = ""
    source_width_px: int = 0
    source_height_px: int = 0

    def add_path(self, path: Path) -> None:
        self.paths.append(path)

    def entity_count(self) -> int:
        return len(self.paths)

    def closed_path_count(self) -> int:
        return sum(1 for p in self.paths if p.closed)

    def open_path_count(self) -> int:
        return sum(1 for p in self.paths if not p.closed)

    def paths_by_layer(self) -> dict[str, list[Path]]:
        layers: dict[str, list[Path]] = {}
        for p in self.paths:
            layers.setdefault(p.layer, []).append(p)
        return layers

    def bounding_box(self) -> tuple[float, float, float, float]:
        if not self.paths:
            return (0, 0, 0, 0)
        all_pts = [pt for p in self.paths for pt in p.points()]
        if not all_pts:
            return (0, 0, 0, 0)
        xs = [pt.x for pt in all_pts]
        ys = [pt.y for pt in all_pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def scale(self, factor: float) -> None:
        for path in self.paths:
            scaled: list[Segment] = []
            for seg in path.segments:
                if isinstance(seg, LineSegment):
                    scaled.append(LineSegment(
                        start=seg.start * factor,
                        end=seg.end * factor,
                    ))
                elif isinstance(seg, ArcSegment):
                    scaled.append(ArcSegment(
                        cx=seg.cx * factor,
                        cy=seg.cy * factor,
                        radius=seg.radius * factor,
                        start_angle=seg.start_angle,
                        end_angle=seg.end_angle,
                        is_counterclockwise=seg.is_counterclockwise,
                    ))
                elif isinstance(seg, BezierSegment):
                    scaled.append(BezierSegment(
                        p0=seg.p0 * factor,
                        p1=seg.p1 * factor,
                        p2=seg.p2 * factor,
                        p3=seg.p3 * factor,
                    ))
            path.segments = scaled

    def detect_open_paths(self, tolerance: float = 0.01) -> list[tuple[int, float]]:
        open_paths: list[tuple[int, float]] = []
        for idx, path in enumerate(self.paths):
            if not path.segments:
                continue
            if not path.closed:
                open_paths.append((idx, 0.0))
                continue
            first_pt = self._first_point(path)
            last_pt = self._last_point(path)
            if first_pt and last_pt:
                gap = (last_pt - first_pt).length()
                if gap > tolerance and path.closed:
                    open_paths.append((idx, gap))
        return open_paths

    def detect_self_intersections(self) -> list[tuple[int, Vec2]]:
        intersections: list[tuple[int, Vec2]] = []
        for idx, path in enumerate(self.paths):
            pts = path.points()
            for i in range(len(pts) - 2):
                for j in range(i + 2, len(pts) - 1):
                    inter = _segment_intersection(
                        pts[i], pts[i + 1], pts[j], pts[j + 1]
                    )
                    if inter is not None:
                        intersections.append((idx, inter))
        return intersections

    def close_gaps(self, max_gap: float = 3.0) -> int:
        closed = 0
        for path in self.paths:
            if not path.closed or not path.segments:
                continue
            first_pt = self._first_point(path)
            last_pt = self._last_point(path)
            if first_pt and last_pt:
                gap = (last_pt - first_pt).length()
                if 0 < gap <= max_gap:
                    path.add_segment(LineSegment(start=last_pt, end=first_pt))
                    closed += 1
        return closed

    def enforce_closed_layer(self, layer: str = "CUT") -> int:
        forced = 0
        for path in self.paths:
            if path.layer == layer and not path.closed:
                path.closed = True
                forced += 1
        return forced

    @staticmethod
    def _first_point(path: Path) -> Vec2 | None:
        if not path.segments:
            return None
        seg = path.segments[0]
        if isinstance(seg, LineSegment):
            return seg.start
        if isinstance(seg, ArcSegment):
            return Vec2(
                seg.cx + seg.radius * math.cos(math.radians(seg.start_angle)),
                seg.cy + seg.radius * math.sin(math.radians(seg.start_angle)),
            )
        if isinstance(seg, BezierSegment):
            return seg.p0
        return None

    @staticmethod
    def _last_point(path: Path) -> Vec2 | None:
        if not path.segments:
            return None
        seg = path.segments[-1]
        if isinstance(seg, LineSegment):
            return seg.end
        if isinstance(seg, ArcSegment):
            theta = math.radians(seg.end_angle)
            return Vec2(
                seg.cx + seg.radius * math.cos(theta),
                seg.cy + seg.radius * math.sin(theta),
            )
        if isinstance(seg, BezierSegment):
            return seg.p3
        return None


def _segment_intersection(
    a1: Vec2, a2: Vec2, b1: Vec2, b2: Vec2
) -> Vec2 | None:
    """Return intersection point of two line segments, or None."""
    d1 = a2 - a1
    d2 = b2 - b1
    cross = d1.cross(d2)
    if abs(cross) < 1e-10:
        return None
    t = (b1 - a1).cross(d2) / cross
    u = (b1 - a1).cross(d1) / cross
    if 0 <= t <= 1 and 0 <= u <= 1:
        return a1 + d1 * t
    return None


def polyline_to_path(
    points: list[tuple[float, float]] | list[list[float]] | list[Vec2],
    closed: bool = True,
    layer: str = "CUT",
    color: int | None = None,
) -> Path:
    if color is None:
        color = LAYER_COLORS.get(layer, 7)
    pts = [
        p if isinstance(p, Vec2) else Vec2(float(p[0]), float(p[1]))
        for p in points
    ]
    path = Path(closed=closed, layer=layer, color=color)
    # Remove consecutive duplicates
    cleaned: list[Vec2] = [pts[0]]
    for p in pts[1:]:
        if p != cleaned[-1]:
            cleaned.append(p)
    for i in range(len(cleaned) - 1):
        path.add_segment(LineSegment(start=cleaned[i], end=cleaned[i + 1]))
    if closed and len(cleaned) > 1:
        gap = (cleaned[-1] - cleaned[0]).length()
        if gap > 1e-6:
            path.add_segment(LineSegment(start=cleaned[-1], end=cleaned[0]))
    return path


def circle_to_path(
    cx: float, cy: float, radius: float,
    layer: str = "CUT",
) -> Path:
    path = Path(closed=True, layer=layer, color=LAYER_COLORS.get(layer, 7))
    path.add_segment(ArcSegment(
        cx=cx, cy=cy, radius=radius,
        start_angle=0.0, end_angle=360.0,
        is_counterclockwise=True,
    ))
    return path
