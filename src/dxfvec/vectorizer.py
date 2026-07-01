"""Universal image vectorizer using OpenCV — NO API calls, 100% free.

Automatically adapts to image type:
  - Drawing/scan  → adaptive threshold (b/w documents, blueprints)
  - Photo/pattern → multi-scale Canny edge fusion (photos, renders, textures)

Produces the canonical PathModel (PRD §7.3) consumed by all exporters.
Integrates QA report generation and tolerance-based node reduction (PRD §3.3 P0).
"""
from __future__ import annotations

import json
import math
import pathlib
from typing import Any, Tuple

import cv2
import numpy as np

from .path_model import (
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
from .qa_report import generate_qa_report, QAReport
from .curve_fitting import detect_and_replace_arcs, douglas_peucker


# ── helpers ──────────────────────────────────────────────────────────────────

def _resize_max_dim(img: np.ndarray, max_dim: int = 2048) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= max_dim:
        return img
    s = max_dim / max(h, w)
    return cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)


def _enhance(img: np.ndarray, clip: float = 2.0) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def _denoise(img: np.ndarray, h: float = 5.0) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(img, None, h, h, 5, 5)


def _deskew(gray: np.ndarray) -> Tuple[np.ndarray, float]:
    gray2 = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY) if gray.ndim == 3 else gray
    edges = cv2.Canny(gray2, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=50)
    if lines is None:
        return gray, 0.0
    angles = []
    for line in lines[:30]:
        rho, theta = line[0]
        ang = (theta - np.pi / 2) * 180.0 / np.pi
        if abs(ang) < 45:
            angles.append(ang)
    if not angles:
        return gray, 0.0
    median = float(np.median(angles))
    if abs(median) < 0.5:
        return gray, 0.0
    h, w = gray2.shape
    M = cv2.getRotationMatrix2D((w // 2, h // 2), median, 1.0)
    return cv2.warpAffine(gray2, M, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE), median


# ── adaptive mode detection ──────────────────────────────────────────────────

def _detect_mode(img_bgr: np.ndarray) -> str:
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    sat_mean = float(np.mean(hsv[:, :, 1]))
    if sat_mean < 8:
        return "drawing"
    return "photo"


# ── photo/pattern preprocessing ──────────────────────────────────────────────

def _preprocess_photo(img_bgr: np.ndarray, out_dir: pathlib.Path) -> np.ndarray:
    out_dir.mkdir(parents=True, exist_ok=True)
    img_bgr = _resize_max_dim(img_bgr)
    enhanced = _enhance(img_bgr)
    denoised = _denoise(enhanced)
    cv2.imwrite(str(out_dir / "preprocessed.png"), denoised)
    gray = cv2.cvtColor(denoised, cv2.COLOR_BGR2GRAY)
    edges = _fuse_canny(gray)
    cv2.imwrite(str(out_dir / "edges.png"), edges)
    return edges


def _fuse_canny(gray: np.ndarray) -> np.ndarray:
    g = cv2.GaussianBlur(gray, (3, 3), 0)
    fused = np.zeros_like(gray, dtype=np.uint8)
    scales = [
        (30, 80),
        (50, 150),
        (80, 250),
    ]
    for lo, hi in scales:
        e = cv2.Canny(g, lo, hi)
        fused = cv2.bitwise_or(fused, e)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    return cv2.morphologyEx(fused, cv2.MORPH_CLOSE, k, iterations=1)


def _merge_nearby_outlines(outlines: list[dict],
                            max_centroid_gap_px: float = 30) -> list[dict]:
    if len(outlines) <= 1:
        return outlines
    centroids = np.array([np.mean(o["points"], axis=0) for o in outlines])
    parent = list(range(len(outlines)))
    rank = [0] * len(outlines)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            parent[ra] = rb
        elif rank[ra] > rank[rb]:
            parent[rb] = ra
        else:
            parent[rb] = ra
            rank[ra] += 1

    for i in range(len(outlines)):
        for j in range(i + 1, len(outlines)):
            if np.linalg.norm(centroids[i] - centroids[j]) <= max_centroid_gap_px:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(outlines)):
        groups.setdefault(find(i), []).append(i)

    merged = []
    for idxs in groups.values():
        if len(idxs) == 1:
            merged.append(outlines[idxs[0]])
            continue
        all_pts = []
        for i in idxs:
            all_pts.extend(outlines[i]["points"])
        arr = np.array(all_pts, dtype=np.float32)
        hull = cv2.convexHull(arr)
        hull_pts = hull.reshape(-1, 2).tolist()
        merged.append({
            "points": hull_pts,
            "closed": True,
            "area": float(cv2.contourArea(hull)),
            "perimeter": float(cv2.arcLength(hull, True)),
        })
    return merged


# ── image modifier ───────────────────────────────────────────────────────────

class ImageModifier:
    @staticmethod
    def load(path: str | pathlib.Path) -> np.ndarray:
        img = cv2.imread(str(path))
        if img is None:
            raise FileNotFoundError(f"Cannot load image: {path}")
        return img

    @staticmethod
    def resize(img: np.ndarray, width=None, height=None, scale=None) -> np.ndarray:
        h, w = img.shape[:2]
        if scale:
            return cv2.resize(img, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_AREA)
        if width:
            return cv2.resize(img, (width, int(h * width / w)),
                              interpolation=cv2.INTER_AREA)
        if height:
            return cv2.resize(img, (int(w * height / h), height),
                              interpolation=cv2.INTER_AREA)
        return img

    @staticmethod
    def enhance_contrast(img: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        l = clahe.apply(l)
        return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    @staticmethod
    def denoise(img: np.ndarray, strength: int = 5) -> np.ndarray:
        return cv2.fastNlMeansDenoisingColored(img, None, strength, strength, 5, 5)

    @staticmethod
    def rotate(img: np.ndarray, angle: float) -> np.ndarray:
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    @staticmethod
    def sharpen(img: np.ndarray) -> np.ndarray:
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        return cv2.filter2D(img, -1, kernel)

    @staticmethod
    def deskew(img: np.ndarray) -> Tuple[np.ndarray, float]:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        return _deskew(gray)

    @staticmethod
    def binarize(img: np.ndarray, method: str = "adaptive",
                 block_size: int = 11, c: int = 2) -> np.ndarray:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        if method == "adaptive":
            return cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, block_size, c)
        if method == "otsu":
            _, binary = cv2.threshold(gray, 0, 255,
                                      cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        return binary


# ── contour utilities ─────────────────────────────────────────────────────────

class ShapeDetector:
    def __init__(self, min_area: int = 100, max_area: int | None = None,
                 retr_mode: int = cv2.RETR_LIST):
        self.min_area = min_area
        self.max_area = max_area or 2_000_000
        self.retr_mode = retr_mode

    def detect_contours(self, binary: np.ndarray) -> list[np.ndarray]:
        contours, _ = cv2.findContours(
            binary, self.retr_mode, cv2.CHAIN_APPROX_SIMPLE)
        return [c for c in contours
                if self.min_area <= cv2.contourArea(c) <= self.max_area]

    @staticmethod
    def detect_outlines(contours: list[np.ndarray],
                        epsilon_ratio: float = 0.015,
                        min_pts: int = 4) -> list[dict]:
        out = []
        for c in contours:
            peri = cv2.arcLength(c, True)
            if peri < 40:
                continue
            approx = cv2.approxPolyDP(c, epsilon_ratio * peri, True)
            if len(approx) >= min_pts or cv2.isContourConvex(approx):
                pts = approx.reshape(-1, 2).tolist()
                if len(pts) >= 3:
                    out.append({"points": pts, "closed": True,
                                "area": float(cv2.contourArea(c)),
                                "perimeter": float(peri)})
        return sorted(out, key=lambda x: x["area"], reverse=True)

    @staticmethod
    def detect_circles(contours: list[np.ndarray], min_r: int = 8, max_r: int = 150) -> Tuple[list[dict], list[np.ndarray]]:
        circles = []
        remaining = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < 50:
                remaining.append(c)
                continue
            perimeter = cv2.arcLength(c, True)
            if perimeter == 0:
                remaining.append(c)
                continue
            circularity = 4.0 * np.pi * area / (perimeter * perimeter)
            if circularity >= 0.78:
                (x, y), radius = cv2.minEnclosingCircle(c)
                if min_r <= radius <= max_r:
                    pts = c.reshape(-1, 2)
                    dists = np.linalg.norm(pts - np.array([x, y]), axis=1)
                    mean_d = np.mean(dists)
                    std_d = np.std(dists)
                    if mean_d > 0 and (std_d / mean_d) < 0.12:
                        circles.append({
                            "cx": float(x),
                            "cy": float(y),
                            "r": float(radius),
                            "area": float(area)
                        })
                        continue
            remaining.append(c)
        return circles, remaining

    @staticmethod
    def detect_lines(binary: np.ndarray, min_len: int = 40) -> list[dict]:
        if binary.dtype != np.uint8:
            binary = binary.astype(np.uint8)
        edges = cv2.Canny(binary, 50, 150)
        raw = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=35,
                               minLineLength=min_len, maxLineGap=6)
        if raw is None:
            return []
        result = []
        for seg in raw:
            x1, y1, x2, y2 = seg[0]
            result.append({"points": [[x1, y1], [x2, y2]],
                           "length": float(np.hypot(x2 - x1, y2 - y1))})
        return result

    @staticmethod
    def detect_polygons(contours: list[np.ndarray],
                        max_sides: int = 12, min_area: int = 200) -> list[dict]:
        polys = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area:
                continue
            peri = cv2.arcLength(c, True)
            if peri < 50:
                continue
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            sides = len(approx)
            if 3 <= sides <= max_sides:
                pts = approx.reshape(-1, 2).tolist()
                x, y, bw, bh = cv2.boundingRect(approx)
                fill_ratio = area / (bw * bh + 1e-6)
                if fill_ratio > 0.25:
                    polys.append({"points": pts, "sides": sides,
                                  "area": float(area), "closed": True})
        return polys

    @staticmethod
    def detect_ellipses(contours: list[np.ndarray]) -> list[dict]:
        ellipses = []
        for c in contours:
            if cv2.contourArea(c) < 300 or len(c) < 5:
                continue
            try:
                el = cv2.fitEllipse(c)
            except cv2.error:
                continue
            area_c = cv2.contourArea(c)
            area_e = np.pi * el[1][0] * el[1][1] / 4
            if area_e > 0 and 0.6 < area_c / area_e < 1.5:
                ellipses.append({"cx": float(el[0][0]), "cy": float(el[0][1]),
                                 "a": float(el[1][0]), "b": float(el[1][1]),
                                 "angle": float(el[2]),
                                 "area": float(area_c)})
        return ellipses


# ── Canonical vectorization pipeline ─────────────────────────────────────────

class Vectorizer:
    """Universal vectorization — produces canonical PathModel + QA report."""

    def __init__(self, min_area: int = 80, simplify_tolerance: float = 1.5,
                 retr_mode: int = cv2.RETR_LIST):
        self.min_area = min_area
        self.simplify_tolerance = simplify_tolerance
        self.retr_mode = retr_mode
        self._mode: str | None = None

    MAX_IMAGE_DIM = 2048

    # ── main entry ──────────────────────────────────────────────────────────

    def preprocess(self, image_path: str | pathlib.Path,
                   output_dir: str | pathlib.Path) -> Tuple[np.ndarray, np.ndarray]:
        output_dir = pathlib.Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        img = ImageModifier.load(image_path)
        h, w = img.shape[:2]
        (output_dir / "original_size.json").write_text(
            json.dumps({"width": w, "height": h}), encoding="utf-8")
        img = _resize_max_dim(img)
        self._mode = _detect_mode(img)
        self.retr_mode = (cv2.RETR_EXTERNAL if self._mode == "photo"
                          else cv2.RETR_LIST)
        if self._mode == "drawing":
            return self._preprocess_drawing(img, output_dir)
        return self._preprocess_photo(img, output_dir)

    def _preprocess_drawing(self, img: np.ndarray,
                            out: pathlib.Path) -> Tuple[np.ndarray, np.ndarray]:
        enhanced = _enhance(img)
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        deskewed, _ = _deskew(gray)
        if deskewed.ndim == 3:
            deskewed = cv2.cvtColor(deskewed, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(deskewed, h=5, templateWindowSize=5,
                                            searchWindowSize=5)
        cv2.imwrite(str(out / "preprocessed.png"), denoised)
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 3)
        if np.mean(binary) < 127:
            binary = cv2.bitwise_not(binary)
        k = np.ones((2, 2), np.uint8)
        binary = cv2.dilate(binary, k, iterations=1)
        cv2.imwrite(str(out / "binary.png"), binary)
        return denoised, binary

    def _preprocess_photo(self, img_bgr: np.ndarray,
                          out: pathlib.Path) -> Tuple[np.ndarray, np.ndarray]:
        edges = _preprocess_photo(img_bgr, out)
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.dilate(edges, k, iterations=1)
        cv2.imwrite(str(out / "binary_edges.png"), binary)
        return edges, binary

    # ── vectorize → PathModel ──────────────────────────────────────────────

    def vectorize(
        self,
        image_path: str | pathlib.Path,
        output_dir: str | pathlib.Path,
        scale_factor: float | None = None,
        calibration: Calibration | None = None,
        tolerance_mm: float = 0.15,
        detect_arcs: bool = True,
        trace_mode: str = "outline",
        dxf_mode: str = "lines",
        dxf_version: str = "R2010",
    ) -> dict[str, Any]:
        output_dir = pathlib.Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        processed, binary = self.preprocess(image_path, output_dir)
        is_drawing = (self._mode == "drawing")

        min_a = self.min_area if is_drawing else max(self.min_area, 200)
        detector = ShapeDetector(min_area=min_a, retr_mode=self.retr_mode)
        contours = detector.detect_contours(binary)
        holes, remaining_contours = detector.detect_circles(contours)
        outlines = detector.detect_outlines(remaining_contours, self.simplify_tolerance)

        if is_drawing:
            polygons = detector.detect_polygons(remaining_contours)
            ellipses = []
        else:
            polygons = []
            ellipses = detector.detect_ellipses(remaining_contours)

        if not is_drawing and len(outlines) > 1:
            outlines = _merge_nearby_outlines(outlines, max_centroid_gap_px=30)

        raw_lines = detector.detect_lines(binary)
        lines = self._dedupe_lines(raw_lines, outlines, binary.shape)

        # Build canonical PathModel
        model = PathModel(
            trace_mode=TraceMode(trace_mode) if trace_mode in ("outline", "centerline") else TraceMode.OUTLINE,
            dxf_mode=DXFMode(dxf_mode) if dxf_mode in ("lines", "hatch", "faces") else DXFMode.LINES,
            dxf_version=DXFVersion(dxf_version) if dxf_version in ("R12", "R2010", "R2018") else DXFVersion.R2010,
            source_image=str(pathlib.Path(image_path).name),
        )

        if calibration and calibration.is_valid:
            model.calibration = calibration

        # Add outlines → CUT layer
        for o in outlines:
            pts = o["points"]
            if tolerance_mm > 0:
                simplified = douglas_peucker(
                    [Vec2(p[0], p[1]) for p in pts],
                    epsilon=tolerance_mm,
                    closed=True,
                )
            else:
                simplified = [Vec2(p[0], p[1]) for p in pts]
            model.add_path(polyline_to_path(
                [(p.x, p.y) for p in simplified],
                closed=True, layer="CUT",
            ))

        # Add holes (circles) → CUT layer
        for h in holes:
            model.add_path(circle_to_path(
                h["cx"], h["cy"], h["r"], layer="CUT",
            ))

        # Add detected lines → CUT layer
        for l in lines:
            pts = l["points"]
            if len(pts) >= 2:
                model.add_path(polyline_to_path(
                    pts, closed=False, layer="CUT",
                ))

        # Add polygons → ENGRAVE layer
        for p in polygons:
            pts = p["points"]
            if tolerance_mm > 0:
                simplified = douglas_peucker(
                    [Vec2(pt[0], pt[1]) for pt in pts],
                    epsilon=tolerance_mm,
                    closed=True,
                )
            else:
                simplified = [Vec2(pt[0], pt[1]) for pt in pts]
            model.add_path(polyline_to_path(
                [(s.x, s.y) for s in simplified],
                closed=True, layer="ENGRAVE",
            ))

        # Add ellipses → ENGRAVE layer
        for el in ellipses:
            cx, cy, a, b, angle = el["cx"], el["cy"], el["a"], el["b"], el.get("angle", 0)
            pts = self._ellipse_to_points(cx, cy, a, b, angle)
            model.add_path(polyline_to_path(pts, closed=True, layer="ENGRAVE"))

        # Arc/circle detection (PRD §3.3 P0)
        if detect_arcs:
            detect_and_replace_arcs(
                model,
                max_deviation=tolerance_mm if tolerance_mm > 0 else 0.5,
            )

        # Apply scale
        if scale_factor is not None and scale_factor != 1.0:
            model.scale(scale_factor)
        elif calibration and calibration.is_valid:
            model.scale(calibration.scale_factor)

        # Write DXF via canonical writer (PRD §3.4 P0)
        from .dxf_writer import write_dxf
        dxf_path = output_dir / "drawing.dxf"
        svg_path = output_dir / "output.svg"

        write_dxf(
            model=model,
            output_path=dxf_path,
            dxf_version=model.dxf_version,
            units=calibration.unit if calibration else "mm",
            enforce_closed_cut=True,
            max_gap_close=3.0 if not dxf_path.exists() else 0.0,
        )

        # Write SVG
        from .dxf_writer import write_svg
        write_svg(model, svg_path)

        # Generate QA report (PRD §3.4 P0)
        qa_report = generate_qa_report(model, dxf_path=dxf_path)

        # Save QA artifacts
        qa_json_path = output_dir / "qa_report.json"
        qa_report.to_json()
        qa_json_path.write_text(qa_report.to_json(), encoding="utf-8")

        qa_md_path = output_dir / "qa_report.md"
        qa_md_path.write_text(qa_report.to_markdown(), encoding="utf-8")

        # Save geometry JSON (backward compat)
        geometry = self._model_to_geometry_dict(model)
        (output_dir / "geometry.json").write_text(
            json.dumps(geometry, indent=2), encoding="utf-8")

        # Save review.md (backward compat)
        self._write_review(model, qa_report, image_path, output_dir / "review.md")

        return {
            "dxf": str(dxf_path),
            "svg": str(svg_path),
            "qa_report": qa_report.to_dict(),
            "qa_report_paths": {
                "json": str(qa_json_path),
                "md": str(qa_md_path),
            },
            "geometry": geometry,
            "model": model,
            "stats": {
                "paths": model.entity_count(),
                "closed": model.closed_path_count(),
                "open": model.open_path_count(),
                "segments": qa_report.total_segments,
                "nodes": qa_report.node_count,
                "layers": len(qa_report.layers),
            },
        }

    @staticmethod
    def _dedupe_lines(raw_lines: list[dict], outlines: list[dict],
                      shape: tuple) -> list[dict]:
        if not raw_lines or not outlines:
            return raw_lines
        h, w = shape[:2]
        kept = []
        edge_img = np.zeros((h, w), dtype=np.uint8)
        for o in outlines:
            pts = np.array(o["points"], dtype=np.int32)
            cv2.polylines(edge_img, [pts], o["closed"], 255, 2)
        for l in raw_lines:
            x1, y1, x2, y2 = [int(v) for v in l["points"][0] + l["points"][1]]
            length = np.hypot(x2 - x1, y2 - y1)
            if length == 0:
                continue
            sample = np.linspace(0, 1, 10)
            ys = np.clip((y1 + sample * (y2 - y1)).astype(int), 0, h - 1)
            xs = np.clip((x1 + sample * (x2 - x1)).astype(int), 0, w - 1)
            if np.mean(edge_img[ys, xs]) > 100:
                continue
            kept.append(l)
        return kept

    @staticmethod
    def _ellipse_to_points(cx: float, cy: float, a: float, b: float,
                           angle_deg: float, n: int = 32) -> list[tuple[float, float]]:
        rad = math.radians(angle_deg)
        pts = []
        for i in range(n):
            theta = 2 * math.pi * i / n
            x = cx + a * math.cos(theta) * math.cos(rad) - b * math.sin(theta) * math.sin(rad)
            y = cy + a * math.cos(theta) * math.sin(rad) + b * math.sin(theta) * math.cos(rad)
            pts.append((x, y))
        return pts

    @staticmethod
    def _model_to_geometry_dict(model: PathModel) -> dict:
        outlines = []
        holes = []
        lines = []
        polygons = []
        ellipses = []
        for path in model.paths:
            pts = [(p.x, p.y) for p in path.points()]
            if len(path.segments) == 1:
                seg = path.segments[0]
                if hasattr(seg, 'is_full_circle') and seg.is_full_circle:
                    holes.append({
                        "cx": seg.cx, "cy": seg.cy, "r": seg.radius,
                        "area": math.pi * seg.radius ** 2,
                    })
                    continue
            if path.layer == "CUT":
                if len(pts) == 2:
                    lines.append({"points": pts, "length": math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])})
                else:
                    outlines.append({"points": pts, "closed": path.closed, "area": 0, "perimeter": 0})
            elif path.layer == "ENGRAVE":
                polygons.append({"points": pts, "closed": path.closed, "sides": len(pts), "area": 0})
            else:
                outlines.append({"points": pts, "closed": path.closed, "area": 0, "perimeter": 0})
        return {
            "outlines": outlines,
            "holes": holes,
            "lines": lines,
            "polygons": polygons,
            "ellipses": ellipses,
            "scale_factor": model.calibration.scale_factor if model.calibration else None,
            "mode": model.trace_mode.value,
        }

    def _write_review(self, model: PathModel, qa: Any, image_path: str | pathlib.Path,
                       output_path: pathlib.Path) -> pathlib.Path:
        cal = model.calibration
        coord = f"{cal.scale_factor:.4f} {cal.unit}/px" if cal and cal.is_valid else "pixel space"
        mode_label = {"drawing": "Drawing/Scan", "photo": "Photo/Pattern"}.get(
            self._mode or "", "Auto")
        md = [
            f"# DXF Vectorization Review — {pathlib.Path(image_path).name}",
            f"\n**Engine:** Classic (OpenCV)  |  **Mode:** {mode_label}  |  **Coords:** {coord}",
            f"\n## QA Summary",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Entities | {qa.entity_count} |",
            f"| Closed | {qa.closed_path_count} |",
            f"| Open | {qa.open_path_count} |",
            f"| Self-intersections | {len(qa.self_intersections)} |",
            f"| DXF audit | {'PASS' if qa.dxf_audit_pass else 'FAIL'} |",
            f"| Layers | {len(qa.layers)} |",
            "\n## Layers\n",
            "| Layer | Entities | ACI |",
            "|---|---|---|",
        ]
        for l in qa.layers:
            md.append(f"| {l.name} | {l.entity_count} | {l.color_aci} |")
        if qa.warnings:
            md.append("\n## Warnings\n")
            for w in qa.warnings:
                md.append(f"- ⚠ {w}")
        output_path.write_text("\n".join(md), encoding="utf-8")
        return output_path


def vectorize_image(image_path: str | pathlib.Path, output_dir: str | pathlib.Path,
                    scale_factor: float | None = None, **kwargs) -> dict:
    vec = Vectorizer(**kwargs)
    return vec.vectorize(image_path, output_dir, scale_factor)


# ── Backward-compatible DXFGenerator ─────────────────────────────────────────

class DXFGenerator:
    """Legacy DXFGenerator for backward compatibility.
    
    Preserves the old API. New code should use the canonical PathModel
    and write_dxf() instead.
    """
    COLORS = {
        "OUTLINE": 1,
        "HOLE": 7,
        "LINE": 3,
        "POLYGON": 5,
        "ELLIPSE": 4,
    }

    def __init__(self):
        import ezdxf
        self.doc = ezdxf.new(dxfversion="R2010")
        self.doc.header["$INSUNITS"] = 4
        for name, color in self.COLORS.items():
            self.doc.layers.add(name, color=color)

    @staticmethod
    def _flatten(pts):
        if not pts:
            return []
        if isinstance(pts[0], dict):
            return [(p["x"], p["y"]) for p in pts]
        return [(p[0], p[1]) for p in pts]

    def add_outline(self, points, closed=True):
        if len(points) < 3:
            return
        self.doc.modelspace().add_lwpolyline(
            self._flatten(points), close=closed,
            dxfattribs={"layer": "OUTLINE", "elevation": 0, "thickness": 0})

    def add_hole(self, cx, cy, r):
        self.doc.modelspace().add_circle(
            (cx, cy, 0), r, dxfattribs={"layer": "HOLE"})

    def add_line(self, points):
        if len(points) < 2:
            return
        a, b = self._flatten(points)[:2]
        self.doc.modelspace().add_line(
            (a[0], a[1], 0), (b[0], b[1], 0),
            dxfattribs={"layer": "LINE"})

    def add_polygon(self, points, closed=True):
        if len(points) < 3:
            return
        self.doc.modelspace().add_lwpolyline(
            self._flatten(points), close=closed,
            dxfattribs={"layer": "POLYGON", "elevation": 0, "thickness": 0})

    def add_ellipse(self, cx, cy, a, b, angle_deg=0.0):
        import math
        ratio = min(b / a, 1.0) if a > 0 else 1.0
        rad = math.radians(angle_deg)
        self.doc.modelspace().add_ellipse(
            (cx, cy, 0),
            major_axis=(a * math.cos(rad), a * math.sin(rad), 0),
            ratio=ratio,
            dxfattribs={"layer": "ELLIPSE"},
        )

    def save(self, path):
        path = pathlib.Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.saveas(str(path))
        return path
