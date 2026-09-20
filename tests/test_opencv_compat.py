"""Regression tests for OpenCV version compatibility.

WHY THIS FILE EXISTS
--------------------
`ClassicEngine` — the default engine — was completely broken on OpenCV 5.x
and no existing test caught it, because every test constructed inputs
directly rather than exercising the OpenCV call path.

The bug: cv2.HoughLinesP returns different array shapes across major
versions.

    OpenCV 4.x:  shape (N, 1, 4)   -> seg[0] yields the 4 coordinates
    OpenCV 5.x:  shape (N, 4)      -> seg[0] yields a single scalar

Code written as `x1, y1, x2, y2 = seg[0]` therefore raises

    TypeError: cannot unpack non-iterable numpy.int32 object

on OpenCV 5.x, at runtime, on the primary code path.

These tests pin the behaviour so it cannot silently break again on the
next major upgrade.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cv2  # noqa: E402

from dxfvec.vectorizer import ShapeDetector  # noqa: E402


def _make_line_image() -> np.ndarray:
    """A black-on-white image containing one long, clear diagonal line."""
    img = np.full((200, 200), 255, dtype=np.uint8)
    cv2.line(img, (20, 20), (180, 180), 0, 3)
    return img


def test_houghlinesp_shape_is_normalised_by_detect_lines():
    """detect_lines must return dicts with 4 coordinates, on any OpenCV."""
    binary = _make_line_image()
    lines = ShapeDetector.detect_lines(binary, min_len=40)

    assert isinstance(lines, list)
    # A single strong diagonal should be detected.
    assert len(lines) >= 1, "expected at least one line from a clear diagonal"

    for entry in lines:
        pts = entry["points"]
        assert len(pts) == 2, f"expected 2 points, got {pts}"
        assert len(pts[0]) == 2 and len(pts[1]) == 2
        # Coordinates must be plain ints, not numpy scalars or arrays.
        for x, y in pts:
            assert isinstance(x, int), f"x is {type(x)}, expected int"
            assert isinstance(y, int), f"y is {type(y)}, expected int"
        assert entry["length"] > 0


def test_detect_lines_returns_empty_on_blank_image():
    """No lines -> empty list, not an exception or [[None]]."""
    blank = np.full((100, 100), 255, dtype=np.uint8)
    assert ShapeDetector.detect_lines(blank, min_len=40) == []


def test_houghlinesp_output_is_reshapable():
    """Guard the exact assumption the fix relies on.

    Whatever shape OpenCV returns, `np.asarray(raw).reshape(-1, 4)` must
    produce an (N, 4) array. If a future OpenCV changes the contract, this
    fails loudly here rather than at runtime in production.
    """
    binary = _make_line_image()
    edges = cv2.Canny(binary, 50, 150)
    raw = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=35, minLineLength=40, maxLineGap=6
    )
    assert raw is not None, "HoughLinesP found nothing in a clear line image"

    normalised = np.asarray(raw).reshape(-1, 4)
    assert normalised.ndim == 2
    assert normalised.shape[1] == 4
    assert normalised.shape[0] >= 1


def test_classic_engine_end_to_end(tmp_path):
    """The default engine must complete on a real image.

    This is the end-to-end guard. It fails on OpenCV 5.x if the
    HoughLinesP shape handling regresses.
    """
    from dxfvec import ClassicEngine

    img_path = tmp_path / "line.png"
    cv2.imwrite(str(img_path), _make_line_image())

    out_dir = tmp_path / "out"
    result = ClassicEngine().convert(str(img_path), out_dir, {})

    assert result is not None, "ClassicEngine.convert returned None"
    # The engine must have produced at least one DXF artefact.
    produced = list(out_dir.rglob("*.dxf"))
    assert produced, f"no DXF written to {out_dir}"
    assert produced[0].stat().st_size > 0, "DXF file is empty"


def test_ezdxf_layer_assignment_api(tmp_path):
    """`ent.dxf.layer = x` works; `ent.dxf['layer'] = x` does not.

    `_apply_cnc_layers` used item assignment, which raises

        TypeError: 'DXFNamespace' object does not support item assignment

    and was swallowed by a broad `except`, so CNC layer naming silently
    never applied. This test documents which API is correct.
    """
    ezdxf = pytest.importorskip("ezdxf")

    doc = ezdxf.new()
    msp = doc.modelspace()
    line = msp.add_line((0, 0), (1, 1))

    line.dxf.layer = "CUT"
    assert line.dxf.layer == "CUT"

    with pytest.raises(TypeError):
        line.dxf["layer"] = "ENGRAVE"
