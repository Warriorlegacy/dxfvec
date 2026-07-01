"""Universal image vectorizer using OpenCV — NO API calls, 100% free.

Automatically adapts to image type:
  • Drawing/scan  → adaptive threshold (b/w documents, blueprints)
  • Photo/pattern → multi-scale Canny edge fusion (photos, renders, textures)
  • No external API keys required.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Tuple

import cv2
import ezdxf
import numpy as np
from ezdxf.enums import TextEntityAlignment


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
    """Correct document rotation using Hough line angles (≤45°). Accepts gray or BGR."""
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
    """Return 'drawing' for clean b/w scans, 'photo' for everything else.

    Key insight: a drawing (black lines on white paper) has no colour
    information at all, so the mean saturation in HSV is essentially 0.
    Photos, renders, textures, and screenshots all have measurable saturation.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    sat_mean = float(np.mean(hsv[:, :, 1]))  # S channel only
    # Also guard: very dark / very bright images without any colour → drawing
    if sat_mean < 8:
        return "drawing"
    return "photo"


# ── photo/pattern preprocessing ──────────────────────────────────────────────

def _preprocess_photo(img_bgr: np.ndarray, out_dir: Path) -> np.ndarray:
    """Multi-scale Canny edge fusion for photos, renders, textures."""
    out_dir.mkdir(parents=True, exist_ok=True)
    img_bgr = _resize_max_dim(img_bgr)
    enhanced = _enhance(img_bgr)
    denoised = _denoise(enhanced)
    cv2.imwrite(str(out_dir / "preprocessed.png"), denoised)
    gray = cv2.cvtColor(denoised, cv2.COLOR_BGR2GRAY)
    # Multi-scale Canny fusion
    edges = _fuse_canny(gray)
    cv2.imwrite(str(out_dir / "edges.png"), edges)
    return edges


def _fuse_canny(gray: np.ndarray) -> np.ndarray:
    """Combine Canny edges at multiple scales for robust detection."""
    g = cv2.GaussianBlur(gray, (3, 3), 0)
    fused = np.zeros_like(gray)
    scales = [
        (30, 80),   # fine — texture, small features
        (50, 150),  # medium — main structure
        (80, 250),  # coarse — big shapes
    ]
    for lo, hi in scales:
        e = cv2.Canny(g, lo, hi)
        fused = cv2.bitwise_or(fused, e)
    # Morphological close gaps
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    return cv2.morphologyEx(fused, cv2.MORPH_CLOSE, k, iterations=1)


def _merge_nearby_outlines(outlines: list[dict],
                            max_centroid_gap_px: float = 30) -> list[dict]:
    """Group nearby outlines and merge each group into its convex hull.

    In photo mode the dilated edge map often splits one physical shape into
    several close contour rings (hatching lines create islands inside the
    outline). This function collapses those rings back into one clean outer
    silhouette so we don't emit dozens of overlapping polylines.
    """
    if len(outlines) <= 1:
        return outlines

    centroids = np.array([np.mean(o["points"], axis=0) for o in outlines])

    # Union-Find to group centroids within max_centroid_gap_px
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


# ── image modifier (kept for backward compat / drawing mode) ─────────────────

class ImageModifier:
    @staticmethod
    def load(path: str | Path) -> np.ndarray:
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
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=50)
        if lines is None:
            return img, 0.0
        angles = []
        for line in lines[:30]:
            rho, theta = line[0]
            ang = (theta - np.pi / 2) * 180.0 / np.pi
            if abs(ang) < 45:
                angles.append(ang)
        if not angles:
            return img, 0.0
        median = float(np.median(angles))
        if abs(median) < 0.5:
            return img, 0.0
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), median, 1.0)
        return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE), median

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
    def detect_circles(binary: np.ndarray, min_r: int = 8, max_r: int = 80,
                       contour_mask: np.ndarray | None = None) -> list[dict]:
        if binary.dtype != np.uint8:
            binary = binary.astype(np.uint8)
        cs = cv2.HoughCircles(binary, cv2.HOUGH_GRADIENT, dp=1, minDist=25,
                               param1=60, param2=35, minRadius=min_r,
                               maxRadius=max_r)
        if cs is None:
            return []
        result = []
        if contour_mask is not None:
            for x, y, r in cs[0]:
                cx, cy = int(x), int(y)
                if 0 <= cy < contour_mask.shape[0] and 0 <= cx < contour_mask.shape[1]:
                    if contour_mask[cy, cx] == 0:
                        continue
                result.append({"cx": float(x), "cy": float(y), "r": float(r),
                               "area": float(np.pi * r * r)})
        else:
            for x, y, r in cs[0]:
                result.append({"cx": float(x), "cy": float(y), "r": float(r),
                               "area": float(np.pi * r * r)})
        return result

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


# ── DXF ──────────────────────────────────────────────────────────────────────

class DXFGenerator:
    COLORS = {
        "OUTLINE": 1,   # Red
        "HOLE": 7,      # White/Black
        "LINE": 3,      # Green
        "POLYGON": 5,   # Blue
        "ELLIPSE": 4,   # Cyan
    }

    def __init__(self):
        self.doc = ezdxf.new(dxfversion="R2010")
        self.doc.header["$INSUNITS"] = 4
        for name, color in self.COLORS.items():
            self.doc.layers.add(name, color=color)

    @staticmethod
    def _flatten(pts):
        """Convert [{"x":..,"y":..}, ...] → [(x,y), ...] for ezdxf."""
        if not pts:
            return []
        if isinstance(pts[0], dict):
            return [(p["x"], p["y"]) for p in pts]
        return [(p[0], p[1]) for p in pts]

    def add_outline(self, points, closed=True):
        if len(points) < 3:
            return
        msp = self.doc.modelspace()
        msp.add_lwpolyline(
            self._flatten(points), close=closed,
            dxfattribs={"layer": "OUTLINE", "elevation": 0, "thickness": 0})

    def add_hole(self, cx, cy, r):
        msp = self.doc.modelspace()
        msp.add_circle((cx, cy, 0), r, dxfattribs={"layer": "HOLE"})

    def add_line(self, points):
        if len(points) < 2:
            return
        msp = self.doc.modelspace()
        a, b = self._flatten(points)[:2]
        msp.add_line((a[0], a[1], 0), (b[0], b[1], 0),
                     dxfattribs={"layer": "LINE"})

    def add_polygon(self, points, closed=True):
        if len(points) < 3:
            return
        msp = self.doc.modelspace()
        msp.add_lwpolyline(
            self._flatten(points), close=closed,
            dxfattribs={"layer": "POLYGON", "elevation": 0, "thickness": 0})

    def add_ellipse(self, cx: float, cy: float, a: float, b: float,
                    angle_deg: float = 0.0):
        msp = self.doc.modelspace()
        ratio = min(b / a, 1.0) if a > 0 else 1.0
        rad = math.radians(angle_deg)
        msp.add_ellipse(
            (cx, cy, 0),
            major_axis=(a * math.cos(rad), a * math.sin(rad), 0),
            ratio=ratio,
            dxfattribs={"layer": "ELLIPSE"},
        )

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.saveas(str(path))
        return path


class Vectorizer:
    """Universal vectorization pipeline — drawing OR photo/pattern mode."""

    def __init__(self, min_area: int = 80, simplify_tolerance: float = 1.5,
                 retr_mode: int = cv2.RETR_LIST):
        self.min_area = min_area
        self.simplify_tolerance = simplify_tolerance
        self.retr_mode = retr_mode
        self._mode: str | None = None

    MAX_IMAGE_DIM = 2048

    # ── main entry ──────────────────────────────────────────────────────────

    def preprocess(self, image_path: str | Path,
                   output_dir: str | Path) -> Tuple[np.ndarray, np.ndarray]:
        """Adaptive preprocessing. Returns (processed_gray_or_edges, binary_map)."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        img = ImageModifier.load(image_path)
        h, w = img.shape[:2]
        (output_dir / "original_size.json").write_text(
            json.dumps({"width": w, "height": h}), encoding="utf-8")

        img = _resize_max_dim(img)
        self._mode = _detect_mode(img)
        # Photo mode: only outer silhouettes — prevents hatching/internal noise
        self.retr_mode = (cv2.RETR_EXTERNAL if self._mode == "photo"
                          else cv2.RETR_LIST)

        if self._mode == "drawing":
            return self._preprocess_drawing(img, output_dir)
        return self._preprocess_photo(img, output_dir)

    def _preprocess_drawing(self, img: np.ndarray,
                            out: Path) -> Tuple[np.ndarray, np.ndarray]:
        """Classic b/w pipeline for clean scans."""
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
                          out: Path) -> Tuple[np.ndarray, np.ndarray]:
        """Multi-scale Canny edge fusion for photos, renders, patterns."""
        edges = _preprocess_photo(img_bgr, out)          # writes preprocessed.png
        # Use the edge map as the "binary" input for contour detection
        # Dilate edges to make thin 1-pixel lines clickable as contours
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.dilate(edges, k, iterations=1)
        cv2.imwrite(str(out / "binary_edges.png"), binary)
        return edges, binary

    # ── vectorize ───────────────────────────────────────────────────────────

    def vectorize(self, image_path: str | Path,
                  output_dir: str | Path,
                  scale_factor: float | None = None) -> dict[str, Any]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        processed, binary = self.preprocess(image_path, output_dir)
        is_drawing = (self._mode == "drawing")

        # Build detector with mode-appropriate retr_mode and min_area
        min_a = self.min_area if is_drawing else max(self.min_area, 200)
        detector = ShapeDetector(min_area=min_a, retr_mode=self.retr_mode)

        # Build a filled-contour mask so circles can check: "am I inside a shape?"
        contour_mask = np.zeros(binary.shape[:2], dtype=np.uint8)
        all_contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(contour_mask, all_contours, -1, 255, thickness=cv2.FILLED)

        contours  = detector.detect_contours(binary)
        outlines  = detector.detect_outlines(contours, self.simplify_tolerance)

        # For drawing mode: polygons from contours; for photo: outline-sized shapes only
        if is_drawing:
            polygons = detector.detect_polygons(contours)
            ellipses = []
        else:
            polygons = []            # outlines capture the filled shapes
            ellipses = detector.detect_ellipses(contours)

        # Photo mode: merge nearby outlines into single large silhouettes
        # so a fragmented hatching boundary collapses into one clean shape
        if not is_drawing and len(outlines) > 1:
            outlines = _merge_nearby_outlines(outlines, max_centroid_gap_px=30)

        # Circles: suppress if centre is inside an existing outline (noise)
        outline_centroids = np.array(
            [np.mean(o["points"], axis=0) for o in outlines], dtype=np.int32)
        suppress = set()
        for ci, co in enumerate(outline_centroids):
            if 0 <= co[1] < contour_mask.shape[0] and 0 <= co[0] < contour_mask.shape[1]:
                if contour_mask[co[1], co[0]] > 0:
                    suppress.add(ci)

        raw_circles = detector.detect_circles(binary, contour_mask=contour_mask)
        holes = [h for i, h in enumerate(raw_circles)
                 if i not in suppress and h["area"] > 500]

        # Lines: filter highly-duplicate segments that overlap outlines
        raw_lines = detector.detect_lines(binary)
        lines = self._dedupe_lines(raw_lines, outlines, binary.shape)

        if scale_factor is not None:
            outlines = self._scale(outlines, "points", scale_factor)
            holes    = self._scale(holes,    ["cx", "cy", "r"], scale_factor)
            lines    = self._scale(lines,    "points", scale_factor)
            polygons = self._scale(polygons, "points", scale_factor)
            ellipses = self._scale_ellipses(ellipses, scale_factor)

        dxf_gen = DXFGenerator()
        for o in outlines:
            dxf_gen.add_outline(o["points"], o["closed"])
        for h in holes:
            dxf_gen.add_hole(h["cx"], h["cy"], h["r"])
        for l in lines:
            dxf_gen.add_line(l["points"])
        for p in polygons:
            dxf_gen.add_polygon(p["points"], p["closed"])
        for el in ellipses:
            dxf_gen.add_ellipse(el["cx"], el["cy"], el["a"], el["b"],
                                el.get("angle", 0))

        dxf_path = dxf_gen.save(output_dir / "drawing.dxf")
        review_path = self._write_review(
            outlines, holes, lines, polygons, ellipses,
            image_path, scale_factor, output_dir / "review.md")

        geometry = self._to_python({
            "outlines": outlines, "holes": holes, "lines": lines,
            "polygons": polygons, "ellipses": ellipses,
            "scale_factor": scale_factor, "mode": self._mode,
        })
        (output_dir / "geometry.json").write_text(
            json.dumps(geometry, indent=2), encoding="utf-8")

        return {
            "dxf": str(dxf_path), "review": str(review_path),
            "geometry": geometry, "stats": {
                "outlines": len(outlines), "holes": len(holes),
                "lines": len(lines),  "polygons": len(polygons),
                "ellipses": len(ellipses),
            },
        }

    @staticmethod
    def _dedupe_lines(raw_lines: list[dict], outlines: list[dict],
                      shape: tuple) -> list[dict]:
        """Remove line segments that are nearly collinear with outline edges."""
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
            # Sample 10 points along the segment, check against edge map
            sample = np.linspace(0, 1, 10)
            ys = np.clip((y1 + sample * (y2 - y1)).astype(int), 0, h - 1)
            xs = np.clip((x1 + sample * (x2 - x1)).astype(int), 0, w - 1)
            if np.mean(edge_img[ys, xs]) > 100:
                continue
            kept.append(l)
        return kept

    @staticmethod
    def _scale(items: list[dict], keys, sf: float) -> list[dict]:
        result = []
        for item in items:
            item = dict(item)
            for k in (keys if isinstance(keys, list) else [keys]):
                if k not in item:
                    continue
                v = item[k]
                if isinstance(v, list) and v and isinstance(v[0], list):
                    item[k] = [[x * sf for x in pt] for pt in v]
                elif isinstance(v, (int, float)):
                    item[k] = v * sf
            result.append(item)
        return result

    @staticmethod
    def _scale_ellipses(ells, sf):
        return [{**e, "cx": e["cx"] * sf, "cy": e["cy"] * sf,
                 "a": e["a"] * sf, "b": e["b"] * sf} for e in ells]

    @staticmethod
    def _to_python(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, list):
            return [Vectorizer._to_python(x) for x in obj]
        if isinstance(obj, dict):
            return {k: Vectorizer._to_python(v) for k, v in obj.items()}
        return obj

    # ── review ──────────────────────────────────────────────────────────────

    def _write_review(self, outlines, holes, lines, polygons, ellipses,
                      image_path, scale_factor, out: Path) -> Path:
        coord = f"{scale_factor:.4f} px/mm (real units)" if scale_factor else "pixel space"
        mode_label = {"drawing": "Drawing/Scan", "photo": "Photo/Pattern"}.get(
            self._mode or "", "Auto")
        md = [
            f"# DXF Vectorization Review — {Path(image_path).name}",
            f"\n**Mode:** {mode_label}  |  **Coords:** {coord}",
            "\n## Geometry detected\n",
            "| Entity  | Count | Layer |",
            "|---------|-------|-------|",
            f"| Outlines| {len(outlines):>5} | OUTLINE |",
            f"| Holes   | {len(holes):>5} | HOLE |",
            f"| Lines   | {len(lines):>5} | LINE |",
            f"| Polygons| {len(polygons):>5} | POLYGON |",
            f"| Ellipses| {len(ellipses):>5} | ELLIPSE |",
            "\n## Mode details\n",
            f"- **{mode_label} mode**: uses {('adaptive threshold' if self._mode == 'drawing' else 'multi-scale Canny edge fusion')}",
            "- 100% local OpenCV processing",
            "- DXF layers: OUTLINE, HOLE, LINE, POLYGON, ELLIPSE",
        ]
        out.write_text("\n".join(md), encoding="utf-8")
        return out


def vectorize_image(image_path: str | Path, output_dir: str | Path,
                    scale_factor: float | None = None, **kwargs) -> dict:
    """One-call vectorization. Detects image type automatically."""
    vec = Vectorizer(**kwargs)
    return vec.vectorize(image_path, output_dir, scale_factor)
