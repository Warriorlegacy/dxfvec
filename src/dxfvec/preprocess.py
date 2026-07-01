"""OpenCV image preprocessing pipeline for engineering drawings.

Steps:
  1. Load → grayscale
  2. CLAHE contrast enhancement
  3. Fast non-local means denoising
  4. Deskew (Hough-based rotation correction)
  5. Optional AI-style edge-aware enhancement (bilateral + mean-shift)
  6. Adaptive binarisation
  7. Invert if needed (dark-on-white = standard engineering drawing)

Returns the preprocessed image as a numpy array and saves to disk.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from dxfvec.ai_enhancer import enhance as _ai_enhance


def preprocess(
    image_path: str | Path,
    output_path: str | Path,
    ai_enhance: bool = False,
    bilateral_d: int = 9,
    mean_shift_radius: int = 7,
    morph_kernel: int = 3,
    deskew_perspective_flag: bool = False,
) -> np.ndarray:
    """Preprocess a raster drawing image and save to output_path."""
    image_path = Path(image_path)
    output_path = Path(output_path)

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot load image: {image_path}")

    # 0. Perspective correction
    if deskew_perspective_flag:
        img = deskew_perspective(img)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. Enhance local contrast (good for faded scans)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 2. Denoise while preserving edges
    denoised = cv2.fastNlMeansDenoising(enhanced, h=5, templateWindowSize=5, searchWindowSize=5)

    # 3. Deskew (simple rotation)
    deskewed = _deskew(denoised)

    # 4. Optional AI-style edge-aware enhancement
    if ai_enhance:
        deskewed = _ai_enhance(
            deskewed,
            bilateral_d=bilateral_d,
            mean_shift_spatial_radius=mean_shift_radius,
            morph_kernel_size=morph_kernel,
        )

    # 5. Adaptive binarisation
    binary = cv2.adaptiveThreshold(
        deskewed, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2,
    )

    # 5. Ensure dark lines on white background
    if np.mean(binary) < 127:
        binary = cv2.bitwise_not(binary)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), binary)
    return binary


def deskew_perspective(img: np.ndarray) -> np.ndarray:
    """Detect the largest quadrilateral contour and warp perspective to make it flat/orthogonal."""
    h, w = img.shape[:2]

    # Convert to grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    best_rect = None
    max_area = 0

    # Method 1: Downscaled Canny + Dilation + Convex Hull (Highly robust for pattern grids/mesh screens)
    try:
        scale = 0.25
        small = cv2.resize(gray, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        edged = cv2.Canny(small, 50, 150)
        
        # Merge edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        dilated = cv2.dilate(edged, kernel, iterations=2)
        closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = sorted(contours, key=cv2.contourArea, reverse=True)[0]
            # Area must be at least 5% of downscaled image
            if cv2.contourArea(c) > (small.shape[0] * small.shape[1] * 0.05):
                hull = cv2.convexHull(c)
                peri = cv2.arcLength(hull, True)
                approx = cv2.approxPolyDP(hull, 0.04 * peri, True)
                if len(approx) == 4:
                    best_rect = approx.reshape(4, 2) / scale
    except Exception:
        pass

    # Method 2: Fallback to direct thresholding/quadrilateral detection if Method 1 didn't yield 4 points
    if best_rect is None:
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        for thresh_val in [50, 80, 120, 160, 200]:
            _, thresh = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

            for c in contours:
                area = cv2.contourArea(c)
                if area < (w * h * 0.05):
                    continue
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                if len(approx) == 4:
                    if area > max_area:
                        if cv2.isContourConvex(approx):
                            max_area = area
                            best_rect = approx.reshape(4, 2)

    # Method 3: Canny on full resolution
    if best_rect is None:
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 30, 200)
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            for c in contours[:5]:
                area = cv2.contourArea(c)
                if area < (w * h * 0.05):
                    continue
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                if len(approx) == 4:
                    if area > max_area:
                        if cv2.isContourConvex(approx):
                            max_area = area
                            best_rect = approx.reshape(4, 2)

    if best_rect is None:
        return img

    # Order corners
    rect = np.zeros((4, 2), dtype="float32")
    s = best_rect.sum(axis=1)
    rect[0] = best_rect[np.argmin(s)]
    rect[2] = best_rect[np.argmax(s)]

    diff = np.diff(best_rect, axis=1)
    rect[1] = best_rect[np.argmin(diff)]
    rect[3] = best_rect[np.argmax(diff)]

    # Skip if detected quadrilateral is just the image boundary itself
    border_tol_w = w * 0.025
    border_tol_h = h * 0.025
    is_boundary = (
        rect[0][0] < border_tol_w and rect[0][1] < border_tol_h and
        rect[1][0] > (w - border_tol_w) and rect[1][1] < border_tol_h and
        rect[2][0] > (w - border_tol_w) and rect[2][1] > (h - border_tol_h) and
        rect[3][0] < border_tol_w and rect[3][1] > (h - border_tol_h)
    )
    if is_boundary:
        return img

    (tl, tr, br, bl) = rect

    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    if maxWidth < 50 or maxHeight < 50:
        return img

    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, M, (maxWidth, maxHeight))


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Correct document rotation using Hough line angles (≤45°)."""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)

    if lines is None:
        return gray

    angles: list[float] = []
    for line in lines[:30]:
        rho, theta = line[0]
        angle = (theta - np.pi / 2) * 180.0 / np.pi
        if abs(angle) < 45:
            angles.append(angle)

    if not angles:
        return gray

    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.5:
        return gray

    h, w = gray.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    return cv2.warpAffine(
        gray, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
