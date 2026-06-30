"""Local image vectorizer using OpenCV — NO API calls, 100% free.

This module performs:
1. Image modification (resize, rotate, enhance, denoise)
2. Edge detection and contour extraction
3. Shape detection (lines, circles, polygons)
4. DXF generation with proper layers

No external API keys required. Everything runs locally.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import ezdxf
import numpy as np
from ezdxf.enums import TextEntityAlignment


class ImageModifier:
    """Image modification and enhancement utilities."""
    
    @staticmethod
    def load(path: str | Path) -> np.ndarray:
        """Load image from file."""
        img = cv2.imread(str(path))
        if img is None:
            raise FileNotFoundError(f"Cannot load image: {path}")
        return img
    
    @staticmethod
    def resize(img: np.ndarray, width: int | None = None, height: int | None = None, 
               scale: float | None = None) -> np.ndarray:
        """Resize image by width, height, or scale factor."""
        h, w = img.shape[:2]
        if scale:
            return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if width:
            ratio = width / w
            return cv2.resize(img, (width, int(h * ratio)), interpolation=cv2.INTER_AREA)
        if height:
            ratio = height / h
            return cv2.resize(img, (int(w * ratio), height), interpolation=cv2.INTER_AREA)
        return img
    
    @staticmethod
    def rotate(img: np.ndarray, angle: float) -> np.ndarray:
        """Rotate image by angle degrees (centered)."""
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    
    @staticmethod
    def enhance_contrast(img: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
        """Enhance contrast using CLAHE (good for faded scans)."""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    @staticmethod
    def denoise(img: np.ndarray, strength: int = 5) -> np.ndarray:
        """Remove noise while preserving edges. Uses light params for web/container use."""
        return cv2.fastNlMeansDenoisingColored(img, None, strength, strength, 5, 5)
    
    @staticmethod
    def sharpen(img: np.ndarray) -> np.ndarray:
        """Sharpen image using unsharp mask."""
        blur = cv2.GaussianBlur(img, (0, 0), 3)
        return cv2.addWeighted(img, 1.5, blur, -0.5, 0)
    
    @staticmethod
    def to_grayscale(img: np.ndarray) -> np.ndarray:
        """Convert to grayscale."""
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img
    
    @staticmethod
    def binarize(img: np.ndarray, method: str = "adaptive", block_size: int = 11, 
                 c: int = 2) -> np.ndarray:
        """Binarize image using various methods."""
        gray = ImageModifier.to_grayscale(img)
        if method == "adaptive":
            return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, block_size, c)
        elif method == "otsu":
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary
        elif method == "simple":
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            return binary
        return gray
    
    @staticmethod
    def deskew(img: np.ndarray) -> tuple[np.ndarray, float]:
        """Correct document rotation using Hough lines. Returns corrected image and angle."""
        gray = ImageModifier.to_grayscale(img)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=50)
        
        if lines is None:
            return img, 0.0
        
        angles = []
        for line in lines[:30]:
            rho, theta = line[0]
            angle = (theta - np.pi / 2) * 180.0 / np.pi
            if abs(angle) < 45:
                angles.append(angle)
        
        if not angles:
            return img, 0.0
        
        median_angle = float(np.median(angles))
        if abs(median_angle) < 0.5:
            return img, 0.0
        
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, 
                                borderMode=cv2.BORDER_REPLICATE)
        return rotated, median_angle


class ShapeDetector:
    """Detect geometric shapes in binary images."""
    
    def __init__(self, min_area: int = 100, max_area: int | None = None):
        self.min_area = min_area
        self.max_area = max_area or (10 ** 6)
    
    def detect_contours(self, binary: np.ndarray) -> list[np.ndarray]:
        """Find all contours in binary image."""
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        return [c for c in contours if self.min_area <= cv2.contourArea(c) <= self.max_area]
    
    def detect_outlines(self, contours: list[np.ndarray]) -> list[dict]:
        """Detect part outlines (closed polygons)."""
        outlines = []
        for contour in contours:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            
            if perimeter == 0:
                continue
            
            # Approximate contour to polygon
            epsilon = 0.02 * perimeter
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # Check if closed
            if cv2.isContourConvex(approx) or len(approx) >= 4:
                points = approx.reshape(-1, 2).tolist()
                outlines.append({
                    "points": points,
                    "closed": True,
                    "area": area,
                    "perimeter": perimeter
                })
        
        return outlines
    
    def detect_circles(self, binary: np.ndarray) -> list[dict]:
        """Detect circular holes using Hough Circle Transform."""
        # Ensure binary is uint8
        if binary.dtype != np.uint8:
            binary = binary.astype(np.uint8)
        
        circles = cv2.HoughCircles(
            binary, cv2.HOUGH_GRADIENT, dp=1, minDist=30,
            param1=50, param2=30, minRadius=5, maxRadius=100
        )
        
        holes = []
        if circles is not None:
            for circle in circles[0]:
                cx, cy, r = circle
                holes.append({
                    "cx": float(cx),
                    "cy": float(cy),
                    "r": float(r),
                    "area": np.pi * r * r
                })
        
        return holes
    
    def detect_lines(self, binary: np.ndarray) -> list[dict]:
        """Detect straight lines using Hough Line Transform."""
        # Ensure binary is uint8
        if binary.dtype != np.uint8:
            binary = binary.astype(np.uint8)
        
        edges = cv2.Canny(binary, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, 
                                minLineLength=30, maxLineGap=10)
        
        result = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
                result.append({
                    "points": [[x1, y1], [x2, y2]],
                    "length": float(length)
                })
        
        return result
    
    def detect_polygons(self, contours: list[np.ndarray], max_sides: int = 12) -> list[dict]:
        """Detect polygonal shapes."""
        polygons = []
        for contour in contours:
            perimeter = cv2.arcLength(contour, True)
            epsilon = 0.02 * perimeter
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            sides = len(approx)
            if 3 <= sides <= max_sides:
                points = approx.reshape(-1, 2).tolist()
                area = cv2.contourArea(contour)
                polygons.append({
                    "points": points,
                    "sides": sides,
                    "area": float(area),
                    "closed": True
                })
        
        return polygons


class DXFGenerator:
    """Generate DXF files from detected geometry."""
    
    # Layer colors (AutoCAD ACI)
    COLORS = {
        "OUTLINE": 1,   # Red
        "HOLE": 7,      # White/Black
        "LINE": 3,      # Green
        "POLYGON": 5,   # Blue
        "BEND": 6,      # Magenta
    }
    
    def __init__(self):
        self.doc = ezdxf.new(dxfversion="R2010")
        self.doc.header["$INSUNITS"] = 4  # mm
        self._setup_layers()
    
    def _setup_layers(self):
        """Create layers with proper colors."""
        for name, color in self.COLORS.items():
            self.doc.layers.add(name, color=color)
    
    def add_outline(self, points: list[list[float]], closed: bool = True):
        """Add part outline to DXF."""
        if len(points) < 2:
            return
        msp = self.doc.modelspace()
        msp.add_lwpolyline(points, close=closed, 
                          dxfattribs={"layer": "OUTLINE"})
    
    def add_hole(self, cx: float, cy: float, r: float):
        """Add circular hole to DXF."""
        msp = self.doc.modelspace()
        msp.add_circle((cx, cy), r, dxfattribs={"layer": "HOLE"})
    
    def add_line(self, points: list[list[float]]):
        """Add straight line to DXF."""
        if len(points) < 2:
            return
        msp = self.doc.modelspace()
        msp.add_line(points[0], points[1], dxfattribs={"layer": "LINE"})
    
    def add_polygon(self, points: list[list[float]], closed: bool = True):
        """Add polygon to DXF."""
        if len(points) < 3:
            return
        msp = self.doc.modelspace()
        msp.add_lwpolyline(points, close=closed, 
                          dxfattribs={"layer": "POLYGON"})
    
    def add_text(self, text: str, position: tuple[float, float], height: float = 2.5):
        """Add text annotation to DXF."""
        msp = self.doc.modelspace()
        msp.add_text(text, dxfattribs={
            "layer": "OUTLINE",
            "height": height,
            "insert": position
        })
    
    def save(self, path: str | Path) -> Path:
        """Save DXF file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.saveas(str(path))
        return path


class Vectorizer:
    """Complete image-to-DXF vectorization pipeline. 100% local, no API calls."""
    
    def __init__(self, min_area: int = 100, simplify_tolerance: float = 0.02):
        self.modifier = ImageModifier()
        self.detector = ShapeDetector(min_area=min_area)
        self.simplify_tolerance = simplify_tolerance
    
    MAX_IMAGE_DIM = 2048

    def preprocess(self, image_path: str | Path, output_dir: str | Path) -> tuple[np.ndarray, np.ndarray]:
        """Preprocess image for vectorization."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        img = self.modifier.load(image_path)

        h, w = img.shape[:2]
        (output_dir / "original_size.json").write_text(
            json.dumps({"width": w, "height": h}), encoding="utf-8"
        )

        max_dim = max(h, w)
        if max_dim > self.MAX_IMAGE_DIM:
            scale_px = self.MAX_IMAGE_DIM / max_dim
            new_w, new_h = int(w * scale_px), int(h * scale_px)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        enhanced = self.modifier.enhance_contrast(img)
        enhanced = self.modifier.sharpen(enhanced)
        deskewed, angle = self.modifier.deskew(enhanced)
        denoised = self.modifier.denoise(deskewed)
        
        # Save preprocessed
        cv2.imwrite(str(output_dir / "preprocessed.png"), denoised)
        
        # Binarize
        binary = self.modifier.binarize(denoised, method="adaptive")
        
        # Ensure dark lines on white background
        if np.mean(binary) < 127:
            binary = cv2.bitwise_not(binary)
        
        cv2.imwrite(str(output_dir / "binary.png"), binary)
        
        return denoised, binary
    
    def vectorize(self, image_path: str | Path, output_dir: str | Path,
                  scale_factor: float | None = None) -> dict[str, Any]:
        """Full vectorization pipeline: image → DXF.
        
        Args:
            image_path: Path to input image
            output_dir: Directory for output files
            scale_factor: Pixels per mm (None = pixel coordinates)
        
        Returns:
            dict with paths and geometry info
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Preprocess
        processed, binary = self.preprocess(image_path, output_dir)
        
        # 2. Detect shapes
        contours = self.detector.detect_contours(binary)
        outlines = self.detector.detect_outlines(contours)
        holes = self.detector.detect_circles(binary)
        lines = self.detector.detect_lines(binary)
        polygons = self.detector.detect_polygons(contours)
        
        # 3. Apply scale if provided
        if scale_factor is not None:
            outlines = self._scale_outlines(outlines, scale_factor)
            holes = self._scale_holes(holes, scale_factor)
            lines = self._scale_lines(lines, scale_factor)
            polygons = self._scale_polygons(polygons, scale_factor)
        
        # 4. Generate DXF
        dxf_gen = DXFGenerator()
        
        for outline in outlines:
            dxf_gen.add_outline(outline["points"], outline["closed"])
        
        for hole in holes:
            dxf_gen.add_hole(hole["cx"], hole["cy"], hole["r"])
        
        for line in lines:
            dxf_gen.add_line(line["points"])
        
        for polygon in polygons:
            dxf_gen.add_polygon(polygon["points"], polygon["closed"])
        
        dxf_path = dxf_gen.save(output_dir / "drawing.dxf")
        
        # 5. Generate review
        review_path = self._write_review(
            outlines, holes, lines, polygons, 
            image_path, scale_factor, output_dir / "review.md"
        )
        
        # 6. Save geometry JSON (convert numpy types to Python types)
        def to_python(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            elif isinstance(obj, (np.floating,)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, list):
                return [to_python(x) for x in obj]
            elif isinstance(obj, dict):
                return {k: to_python(v) for k, v in obj.items()}
            return obj
        
        geometry = to_python({
            "outlines": outlines,
            "holes": holes,
            "lines": lines,
            "polygons": polygons,
            "scale_factor": scale_factor
        })
        (output_dir / "geometry.json").write_text(
            json.dumps(geometry, indent=2), encoding="utf-8"
        )
        
        return {
            "dxf": str(dxf_path),
            "review": str(review_path),
            "geometry": geometry,
            "stats": {
                "outlines": len(outlines),
                "holes": len(holes),
                "lines": len(lines),
                "polygons": len(polygons)
            }
        }
    
    def _scale_outlines(self, outlines: list[dict], factor: float) -> list[dict]:
        for outline in outlines:
            outline["points"] = [[x * factor, y * factor] for x, y in outline["points"]]
        return outlines
    
    def _scale_holes(self, holes: list[dict], factor: float) -> list[dict]:
        for hole in holes:
            hole["cx"] *= factor
            hole["cy"] *= factor
            hole["r"] *= factor
        return holes
    
    def _scale_lines(self, lines: list[dict], factor: float) -> list[dict]:
        for line in lines:
            line["points"] = [[x * factor, y * factor] for x, y in line["points"]]
        return lines
    
    def _scale_polygons(self, polygons: list[dict], factor: float) -> list[dict]:
        for poly in polygons:
            poly["points"] = [[x * factor, y * factor] for x, y in poly["points"]]
        return polygons
    
    def _write_review(self, outlines, holes, lines, polygons, 
                      image_path, scale_factor, output_path: Path) -> Path:
        """Write review report."""
        coord_mode = f"{scale_factor:.4f} px/mm (real units)" if scale_factor else "pixel space"
        
        lines_md = [
            f"# DXF Vectorization Review — {Path(image_path).name}",
            f"\n**Mode:** Local OpenCV (no API)  |  **Coords:** {coord_mode}",
            "\n## Geometry detected\n",
            "| Entity type | Count | Layer |",
            "|-------------|-------|-------|",
            f"| Outlines    | {len(outlines):>5} | OUTLINE |",
            f"| Holes       | {len(holes):>5} | HOLE |",
            f"| Lines       | {len(lines):>5} | LINE |",
            f"| Polygons    | {len(polygons):>5} | POLYGON |",
            "\n## Features\n",
            "- 100% local processing (no API calls)",
            "- Automatic edge detection and contour extraction",
            "- Shape classification (outlines, holes, lines, polygons)",
            "- DXF layers for CAD/CAM workflows",
        ]
        
        output_path.write_text("\n".join(lines_md), encoding="utf-8")
        return output_path


# Convenience function
def vectorize_image(image_path: str | Path, output_dir: str | Path,
                    scale_factor: float | None = None, **kwargs) -> dict:
    """One-call vectorization. No API keys needed."""
    vec = Vectorizer(**kwargs)
    return vec.vectorize(image_path, output_dir, scale_factor)
