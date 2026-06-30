"""OpenCV image preprocessing pipeline for engineering drawings.

Steps:
  1. Load → grayscale
  2. CLAHE contrast enhancement
  3. Fast non-local means denoising
  4. Deskew (Hough-based rotation correction)
  5. Adaptive binarisation
  6. Invert if needed (dark-on-white = standard engineering drawing)

Returns the preprocessed image as a numpy array and saves to disk.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def preprocess(image_path: str | Path, output_path: str | Path) -> np.ndarray:
    """Preprocess a raster drawing image and save to output_path."""
    image_path = Path(image_path)
    output_path = Path(output_path)

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot load image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. Enhance local contrast (good for faded scans)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 2. Denoise while preserving edges
    denoised = cv2.fastNlMeansDenoising(enhanced, h=5, templateWindowSize=5, searchWindowSize=5)

    # 3. Deskew
    deskewed = _deskew(denoised)

    # 4. Adaptive binarisation
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
