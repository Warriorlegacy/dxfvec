"""Quality Assurance report generation and DXF validation for dxfvec.

Implements the QAReport data model from PRD §5.1, providing:
  - Entity counting and classification
  - Open path detection with gap locations
  - Self-intersection detection
  - Bounding box computation
  - DXF audit via ezdxf.doc.audit()
  - Human-readable and machine-readable (JSON) output

Every export MUST have an accompanying QA report before download is
presented to the user (PRD §3.4, P0).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ezdxf

from .path_model import PathModel, Vec2


@dataclass
class OpenPathInfo:
    path_index: int
    gap_mm: float
    location_x: float
    location_y: float


@dataclass
class SelfIntersectionInfo:
    path_index: int
    x: float
    y: float


@dataclass
class LayerInfo:
    name: str
    entity_count: int
    color_aci: int


@dataclass
class QAReport:
    entity_count: int = 0
    closed_path_count: int = 0
    open_path_count: int = 0
    open_paths: list[OpenPathInfo] = field(default_factory=list)
    self_intersections: list[SelfIntersectionInfo] = field(default_factory=list)
    bounding_box: dict[str, float] = field(default_factory=lambda: {
        "min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "unit": "mm"
    })
    estimated_dimensional_accuracy_pct: float = 100.0
    dxf_audit_pass: bool = False
    dxf_audit_errors: list[str] = field(default_factory=list)
    layers: list[LayerInfo] = field(default_factory=list)
    total_segments: int = 0
    node_count: int = 0
    warnings: list[str] = field(default_factory=list)
    is_calibrated: bool = False
    calibration_unit: str = "px"
    report_timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_markdown(self) -> str:
        lines = [
            "# QA Report",
            f"\n**Generated:** {self.report_timestamp or 'N/A'}",
            f"**Calibrated:** {'Yes' if self.is_calibrated else 'No (pixel-space only)'}",
            f"**Unit:** {self.calibration_unit}",
            "",
            "## Summary",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Entities | {self.entity_count} |",
            f"| Closed paths | {self.closed_path_count} |",
            f"| Open paths | {self.open_path_count} |",
            f"| Total segments | {self.total_segments} |",
            f"| Node count | {self.node_count} |",
            f"| Self-intersections | {len(self.self_intersections)} |",
            f"| DXF audit | {'✅ PASS' if self.dxf_audit_pass else '❌ FAIL'} |",
        ]

        bb = self.bounding_box
        lines.append("")
        lines.append("## Bounding Box")
        lines.append(
            f"| X: {bb.get('min_x', 0):.2f} – {bb.get('max_x', 0):.2f} "
            f"| Y: {bb.get('min_y', 0):.2f} – {bb.get('max_y', 0):.2f} "
            f"| Unit: {bb.get('unit', 'px')} |"
        )
        if self.estimated_dimensional_accuracy_pct < 100:
            lines.append(f"\n**Dimensional accuracy:** {self.estimated_dimensional_accuracy_pct:.1f}%")

        if self.warnings:
            lines.append("")
            lines.append("## Warnings")
            for w in self.warnings:
                lines.append(f"- ⚠ {w}")

        if self.open_paths:
            lines.append("")
            lines.append("## Open Paths")
            for op in self.open_paths:
                lines.append(f"- Path #{op.path_index}: {op.gap_mm:.2f}mm gap at ({op.location_x:.1f}, {op.location_y:.1f})")

        if self.self_intersections:
            lines.append("")
            lines.append("## Self-Intersections")
            for si in self.self_intersections:
                lines.append(f"- Path #{si.path_index}: at ({si.x:.1f}, {si.y:.1f})")

        if self.layers:
            lines.append("")
            lines.append("## Layers")
            lines.append("| Layer | Entities | ACI Color |")
            lines.append("|---|---|---|")
            for l in self.layers:
                lines.append(f"| {l.name} | {l.entity_count} | {l.color_aci} |")

        if self.dxf_audit_errors:
            lines.append("")
            lines.append("## DXF Audit Errors")
            for e in self.dxf_audit_errors:
                lines.append(f"- {e}")

        lines.append("")
        lines.append("---")
        lines.append(f"*dxfvec QA report - {self.report_timestamp}*")
        return "\n".join(lines)

    def has_critical_issues(self) -> bool:
        return (
            not self.dxf_audit_pass
            or self.open_path_count > 0
        )

    def passes_ga_criteria(self) -> bool:
        return (
            self.dxf_audit_pass
            and self.open_path_count == 0
            and len(self.self_intersections) == 0
        )


def generate_qa_report(
    model: PathModel,
    dxf_path: str | Path | None = None,
    open_path_tolerance: float = 0.01,
    max_acceptable_gap: float = 3.0,
) -> QAReport:
    report = QAReport()
    report.report_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report.entity_count = model.entity_count()
    report.closed_path_count = model.closed_path_count()
    report.open_path_count = 0  # will be set below after detection
    report.is_calibrated = model.calibration is not None and model.calibration.is_valid
    report.calibration_unit = model.calibration.unit if model.calibration else "px"

    total_segments = 0
    node_count = 0
    for path in model.paths:
        total_segments += path.segment_count()
        node_count += len(path.points())
    report.total_segments = total_segments
    report.node_count = node_count

    # Bounding box
    bb = model.bounding_box()
    report.bounding_box = {
        "min_x": round(bb[0], 4),
        "min_y": round(bb[1], 4),
        "max_x": round(bb[2], 4),
        "max_y": round(bb[3], 4),
        "unit": report.calibration_unit,
    }

    # Open path detection on intended-closed paths
    open_paths = model.detect_open_paths(tolerance=open_path_tolerance)
    report.open_path_count = len(open_paths)
    for idx, gap in open_paths:
        pts = model.paths[idx].points()
        loc = pts[-1] if pts else Vec2(0, 0)
        report.open_paths.append(OpenPathInfo(
            path_index=idx,
            gap_mm=round(gap, 4),
            location_x=round(loc.x, 2),
            location_y=round(loc.y, 2),
        ))

    # Self-intersection detection
    si_list = model.detect_self_intersections()
    for idx, pt in si_list:
        report.self_intersections.append(SelfIntersectionInfo(
            path_index=idx,
            x=round(pt.x, 2),
            y=round(pt.y, 2),
        ))

    # Layer info
    for name, paths in model.paths_by_layer().items():
        aci = 7
        try:
            from .path_model import LAYER_COLORS
            aci = LAYER_COLORS.get(name, 7)
        except ImportError:
            pass
        report.layers.append(LayerInfo(
            name=name,
            entity_count=len(paths),
            color_aci=aci,
        ))

    # Dimensional accuracy estimate (pessimistic if uncalibrated)
    if model.calibration and model.calibration.is_valid:
        if model.calibration.scale_factor > 0:
            report.estimated_dimensional_accuracy_pct = 99.5
    else:
        report.estimated_dimensional_accuracy_pct = 0.0
        report.warnings.append(
            "No calibration provided. Output is in pixel-space - "
            "not real-world dimensions. Use the calibration tool for accurate scaling."
        )

    # DXF audit (if path provided)
    if dxf_path:
        _run_dxf_audit(report, dxf_path)

    # Warning generation
    if report.open_path_count > 0:
        report.warnings.append(
            f"{report.open_path_count} open path(s) detected. "
            "Open paths may cause cutter/CNC errors. Use 'Auto-fix' to bridge gaps."
        )
    if report.self_intersections:
        report.warnings.append(
            f"{len(report.self_intersections)} self-intersection(s) detected. "
            "Self-intersecting paths may produce unexpected CAM behavior."
        )
    if not report.dxf_audit_pass and dxf_path:
        report.warnings.append(
            "DXF audit failed. The file may not open correctly in all CAD tools."
        )
    if not model.paths:
        report.warnings.append(
            "No vector entities generated. Try adjusting the threshold or "
            "switching to a different engine mode."
        )

    return report


def _run_dxf_audit(report: QAReport, dxf_path: str | Path) -> None:
    try:
        doc = ezdxf.readfile(str(dxf_path))
        auditor = doc.audit()
        critical_errors = [
            e for e in auditor.errors
            if e.get("severity", 0) >= 50
        ]
        report.dxf_audit_pass = len(critical_errors) == 0
        report.dxf_audit_errors = [
            str(e) for e in auditor.errors
        ]
    except Exception as e:
        report.dxf_audit_pass = False
        report.dxf_audit_errors.append(f"DXF read error: {e}")


def save_qa_report(report: QAReport, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix == ".json":
        output_path.write_text(report.to_json(), encoding="utf-8")
    else:
        output_path.write_text(report.to_markdown(), encoding="utf-8")
    return output_path
