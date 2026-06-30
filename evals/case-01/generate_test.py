"""
Generate a synthetic engineering drawing for dxfvec testing.

Produces test_drawing.png — a clean line drawing simulating a metal part with:
  - Rectangular outline (200mm × 120mm equivalent)
  - Two circular holes Ø20mm
  - One dashed center/bend line
  - Width and height dimension annotations
  - Light noise to simulate a real scan

Run: python generate_test.py
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def generate(output_path: str | Path = "test_drawing.png") -> str:
    output_path = Path(output_path)
    img = np.ones((460, 660, 3), dtype=np.uint8) * 255  # white background

    # Part outline
    cv2.rectangle(img, (80, 80), (560, 340), (0, 0, 0), 2)

    # Circular holes
    cv2.circle(img, (170, 210), 32, (0, 0, 0), 2)
    cv2.circle(img, (470, 210), 32, (0, 0, 0), 2)

    # Dashed center / bend line (horizontal)
    for x in range(80, 560, 22):
        cv2.line(img, (x, 210), (min(x + 14, 560), 210), (0, 0, 0), 1)

    # Width dimension
    cv2.line(img, (80, 375), (560, 375), (100, 100, 100), 1)
    cv2.arrowedLine(img, (320, 375), (80, 375),  (100, 100, 100), 1, tipLength=0.04)
    cv2.arrowedLine(img, (320, 375), (560, 375), (100, 100, 100), 1, tipLength=0.04)
    cv2.putText(img, "200mm", (262, 370), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)

    # Height dimension
    cv2.line(img, (590, 80), (590, 340), (100, 100, 100), 1)
    cv2.arrowedLine(img, (590, 210), (590, 80),  (100, 100, 100), 1, tipLength=0.04)
    cv2.arrowedLine(img, (590, 210), (590, 340), (100, 100, 100), 1, tipLength=0.04)
    cv2.putText(img, "120mm", (596, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)

    # Hole diameter callouts
    cv2.putText(img, "2x  O20mm", (245, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 1)

    # Title block (simple)
    cv2.rectangle(img, (80, 400), (560, 440), (0, 0, 0), 1)
    cv2.putText(img, "PART: TEST-001   MATERIAL: SS304   SCALE: 1:1", (90, 426),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 0, 0), 1)

    # Light scan noise
    noise = np.random.randint(0, 6, img.shape, dtype=np.uint8)
    img = cv2.subtract(img, noise)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), img)
    print(f"✅  Test drawing saved: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    generate(Path(__file__).parent / "test_drawing.png")
