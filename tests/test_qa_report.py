"""Unit tests for the QA Report system — PRD §3.4 P0."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dxfvec.path_model import (
    Calibration,
    PathModel,
    Vec2,
    polyline_to_path,
    circle_to_path,
)
from dxfvec.qa_report import (
    QAReport,
    generate_qa_report,
    save_qa_report,
    OpenPathInfo,
    SelfIntersectionInfo,
    LayerInfo,
)
from dxfvec.dxf_writer import write_dxf


def test_qa_report_empty():
    model = PathModel()
    report = generate_qa_report(model)
    assert report.entity_count == 0
    assert report.closed_path_count == 0
    assert report.open_path_count == 0
    assert len(report.warnings) > 0
    assert report.dxf_audit_pass is False


def test_qa_report_with_paths():
    model = PathModel()
    model.add_path(polyline_to_path([(0, 0), (10, 0), (10, 10), (0, 10)], closed=True, layer="CUT"))
    model.add_path(polyline_to_path([(20, 20), (30, 20)], closed=False, layer="CUT"))
    model.add_path(circle_to_path(50, 50, 5, layer="CUT"))

    report = generate_qa_report(model)
    assert report.entity_count == 3
    assert report.closed_path_count == 2
    assert report.open_path_count == 1
    bb = report.bounding_box
    assert bb["min_x"] >= 0
    assert bb["max_x"] >= 10
    assert len(report.layers) == 1


def test_qa_report_with_calibration():
    model = PathModel()
    model.calibration = Calibration(reference_px_length=100, real_world_length=50, unit="mm")
    model.add_path(polyline_to_path([(0, 0), (10, 0), (10, 10), (0, 10)], closed=True))

    report = generate_qa_report(model)
    assert report.is_calibrated is True
    assert report.calibration_unit == "mm"
    assert report.estimated_dimensional_accuracy_pct > 90


def test_qa_report_uncalibrated():
    model = PathModel()
    model.add_path(polyline_to_path([(0, 0), (10, 0), (10, 10)], closed=True))

    report = generate_qa_report(model)
    assert report.is_calibrated is False
    assert report.calibration_unit == "px"
    assert report.estimated_dimensional_accuracy_pct == 0.0
    has_no_cal_warning = any("No calibration" in w for w in report.warnings)
    assert has_no_cal_warning


def test_qa_report_to_json():
    report = QAReport(
        entity_count=5,
        closed_path_count=4,
        open_path_count=1,
        dxf_audit_pass=True,
    )
    json_str = report.to_json()
    assert '"entity_count": 5' in json_str
    assert '"closed_path_count": 4' in json_str
    assert '"dxf_audit_pass": true' in json_str


def test_qa_report_to_markdown():
    report = QAReport(entity_count=3, dxf_audit_pass=True)
    md = report.to_markdown()
    assert "QA Report" in md
    assert "3" in md
    assert "PASS" in md


def test_qa_report_critical():
    report = QAReport(dxf_audit_pass=False, open_path_count=2)
    assert report.has_critical_issues() is True

    report2 = QAReport(dxf_audit_pass=True, open_path_count=0, self_intersections=[])
    assert report2.passes_ga_criteria() is True


def test_qa_report_dxf_audit():
    model = PathModel()
    model.add_path(polyline_to_path([(0, 0), (100, 0), (100, 100), (0, 100)], closed=True))
    model.calibration = Calibration(100, 100, "mm")

    with tempfile.TemporaryDirectory() as tmp:
        dxf_path = Path(tmp) / "test.dxf"
        write_dxf(model, dxf_path, enforce_closed_cut=True)
        report = generate_qa_report(model, dxf_path=dxf_path)
        assert report.dxf_audit_pass is True


def test_save_qa_report():
    report = QAReport(entity_count=1, dxf_audit_pass=True)
    with tempfile.TemporaryDirectory() as tmp:
        json_path = Path(tmp) / "report.json"
        save_qa_report(report, json_path)
        assert json_path.exists()
        content = json_path.read_text()
        assert "entity_count" in content

        md_path = Path(tmp) / "report.md"
        save_qa_report(report, md_path)
        assert md_path.exists()


def test_open_path_info():
    op = OpenPathInfo(path_index=0, gap_mm=2.5, location_x=10, location_y=20)
    assert op.path_index == 0
    assert op.gap_mm == 2.5


def test_self_intersection_info():
    si = SelfIntersectionInfo(path_index=1, x=5.5, y=6.5)
    assert si.path_index == 1
    assert si.x == 5.5


def test_layer_info():
    li = LayerInfo(name="CUT", entity_count=5, color_aci=1)
    assert li.name == "CUT"
    assert li.entity_count == 5
    assert li.color_aci == 1


if __name__ == "__main__":
    test_qa_report_empty()
    test_qa_report_with_paths()
    test_qa_report_with_calibration()
    test_qa_report_uncalibrated()
    test_qa_report_to_json()
    test_qa_report_to_markdown()
    test_qa_report_critical()
    test_qa_report_dxf_audit()
    test_save_qa_report()
    test_open_path_info()
    test_self_intersection_info()
    test_layer_info()
    print("ALL qa_report tests PASSED")
