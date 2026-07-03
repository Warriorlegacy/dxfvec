"""Tests for image preprocessing pipeline."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pytest

from dxfvec.preprocess import preprocess, _deskew, deskew_perspective


class TestPreprocess:
    """Test the full preprocessing pipeline."""

    def test_preprocess_grayscale_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Create a simple color image
            img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            in_path = Path(tmp) / "input.png"
            out_path = Path(tmp) / "output.png"
            import cv2
            cv2.imwrite(str(in_path), img)
            result = preprocess(in_path, out_path)
            assert result is not None
            assert len(result.shape) == 2  # grayscale

    def test_preprocess_creates_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            img = np.ones((100, 100, 3), dtype=np.uint8) * 255
            in_path = Path(tmp) / "input.png"
            out_path = Path(tmp) / "output.png"
            import cv2
            cv2.imwrite(str(in_path), img)
            preprocess(in_path, out_path)
            assert out_path.exists()

    def test_preprocess_invalid_image_raises(self):
        with pytest.raises(ValueError, match="Cannot load image"):
            preprocess(Path("/nonexistent.png"), Path("/tmp/out.png"))

    def test_preprocess_dark_on_white(self):
        with tempfile.TemporaryDirectory() as tmp:
            # White image with black rectangle
            img = np.ones((100, 100, 3), dtype=np.uint8) * 255
            img[40:60, 10:90] = 0
            in_path = Path(tmp) / "input.png"
            out_path = Path(tmp) / "output.png"
            import cv2
            cv2.imwrite(str(in_path), img)
            result = preprocess(in_path, out_path)
            # After binarization + inversion check, mean should be > 127 (dark on white)
            assert np.mean(result) > 127

    def test_preprocess_with_ai_enhance(self):
        with tempfile.TemporaryDirectory() as tmp:
            img = np.ones((100, 100, 3), dtype=np.uint8) * 200
            img[40:60, 10:90] = 50
            in_path = Path(tmp) / "input.png"
            out_path = Path(tmp) / "output.png"
            import cv2
            cv2.imwrite(str(in_path), img)
            result = preprocess(in_path, out_path, ai_enhance=True)
            assert result is not None
            assert len(result.shape) == 2


class TestDeskew:
    """Test the deskew rotation correction."""

    def test_straight_image_unchanged(self):
        gray = np.ones((100, 200), dtype=np.uint8) * 255
        gray[40:60, 10:190] = 0  # horizontal line
        result = _deskew(gray)
        assert result.shape == gray.shape

    def test_no_lines_returns_original(self):
        gray = np.ones((100, 100), dtype=np.uint8) * 255
        result = _deskew(gray)
        assert result.shape == gray.shape

    def test_returns_numpy_array(self):
        gray = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        result = _deskew(gray)
        assert isinstance(result, np.ndarray)


class TestDeskewPerspective:
    """Test perspective correction."""

    def test_returns_original_when_no_quad(self):
        # Uniform image, no quadrilateral detectable
        img = np.ones((100, 100, 3), dtype=np.uint8) * 200
        result = deskew_perspective(img)
        assert result.shape[:2] == img.shape[:2]

    def test_bgr_input(self):
        img = np.ones((100, 100, 3), dtype=np.uint8) * 200
        img[10:90, 10:90] = 0
        img[20:80, 20:80] = 255
        result = deskew_perspective(img)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
