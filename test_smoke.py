"""Smoke test for dxfvec v1.0 — imports and basic functionality."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

errors = []

# 1. Package imports
print("[1] Importing package...")
try:
    import dxfvec
    from dxfvec.engines import ClassicEngine, AdvancedEngine, PRESETS, list_presets, apply_preset
    from dxfvec.cloud_providers import get_cloud_provider, list_cloud_providers, get_api_key
    from dxfvec.dxf_writer import create_dxf
    from dxfvec.vectorizer import vectorize_image
    print("    OK — all imports succeeded")
except Exception as e:
    errors.append(f"Import failed: {e}")
    print(f"    FAIL: {e}")

# 2. Presets
print("[2] Checking presets...")
expected = {"logo_engrave", "laser_stencil", "technical_drawing", "contour_map"}
actual = set(PRESETS.keys())
if expected == actual:
    print(f"    OK — {len(PRESETS)} presets found")
else:
    missing = expected - actual
    extra = actual - expected
    msg = f"Missing: {missing}, Extra: {extra}"
    errors.append(msg)
    print(f"    FAIL: {msg}")

# 3. Cloud provider registry
print("[3] Checking cloud providers...")
from dxfvec.cloud_providers import CLOUD_PROVIDERS
expected_providers = {"vectorizer_ai", "dxfai"}
actual_providers = set(CLOUD_PROVIDERS.keys())
if expected_providers == actual_providers:
    print(f"    OK — {len(CLOUD_PROVIDERS)} providers registered")
else:
    missing = expected_providers - actual_providers
    msg = f"Missing providers: {missing}"
    errors.append(msg)
    print(f"    FAIL: {msg}")

# 4. Classic engine instantiation
print("[4] Classic engine instantiation...")
try:
    engine = ClassicEngine()
    assert engine.name == "classic"
    print("    OK — ClassicEngine() works")
except Exception as e:
    errors.append(f"ClassicEngine failed: {e}")
    print(f"    FAIL: {e}")

# 5. Advanced engine instantiation
print("[5] Advanced engine instantiation...")
try:
    engine = AdvancedEngine()
    assert engine.name == "advanced"
    print("    OK — AdvancedEngine() works")
except Exception as e:
    errors.append(f"AdvancedEngine failed: {e}")
    print(f"    FAIL: {e}")

# 6. create_dxf with mode parameter
print("[6] DXF writer modes...")
try:
    import ezdxf
    geometry = {
        "outlines": [{"points": [[0,0],[100,0],[100,100],[0,100]], "closed": True}],
        "holes": [],
        "bend_lines": [],
        "dimensions": [],
        "polygons": [],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        for mode in ("lines", "hatch", "faces"):
            out = Path(tmpdir) / f"test_{mode}.dxf"
            create_dxf(geometry, out, dxf_mode=mode)
            assert out.exists(), f"DXF not created for mode={mode}"
            doc = ezdxf.readfile(str(out))
            layers = [e.dxf.get("layer", "0") for e in doc.modelspace()]
            print(f"    mode={mode}: {len(layers)} entities, layers={set(layers)}")
    print("    OK — all DXF modes work")
except Exception as e:
    errors.append(f"DXF modes failed: {e}")
    print(f"    FAIL: {e}")

# 7. apply_preset
print("[7] Preset application...")
try:
    base = {"min_area": 100, "simplify_tolerance": 1.5}
    updated = apply_preset(base, "logo_engrave")
    assert updated.get("preset") == "logo_engrave", "preset key missing"
    assert updated.get("min_area") == 50, f"min_area wrong: {updated.get('min_area')}"
    print(f"    OK — preset applied: {updated.get('preset')}, min_area={updated.get('min_area')}")
except Exception as e:
    errors.append(f"apply_preset failed: {e}")
    print(f"    FAIL: {e}")

# Summary
print("\n" + "=" * 50)
if errors:
    print(f"RESULT: FAIL — {len(errors)} issue(s)")
    for err in errors:
        print(f"  * {err}")
    sys.exit(1)
else:
    print("RESULT: PASS — all smoke tests succeeded")
    sys.exit(0)
