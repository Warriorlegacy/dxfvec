"""Multi-agent DXF conversion pipeline using CrewAI.

Three specialized agents run sequentially:
  1. Vision Analyst     — reads the drawing, extracts geometry JSON
  2. DXF Builder        — converts geometry JSON → drawing.dxf via ezdxf
  3. QA Reviewer        — verifies the DXF and writes review.md

Any vision-capable LLM works as the backend (provider arg → LiteLLM model string).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from crewai import Agent, Crew, Process, Task
from crewai.tools import BaseTool
from pydantic import Field

from .dxf_writer import create_dxf
from .preprocess import preprocess
from .providers import resolve_model


# ── Custom tools ────────────────────────────────────────────────────────────

class DXFWriterTool(BaseTool):
    name: str = "write_dxf"
    description: str = (
        "Write a DXF file from a geometry JSON string. "
        "Input must be a JSON string with keys: outlines, holes, bend_lines, dimensions. "
        "Returns the absolute path to the saved .dxf file."
    )
    output_dir: str = Field(default="/tmp/dxf_output")

    def _run(self, geometry_json: str) -> str:
        geometry = json.loads(geometry_json)
        out = Path(self.output_dir) / "drawing.dxf"
        create_dxf(geometry, out)
        return str(out)


class WriteFileTool(BaseTool):
    name: str = "write_file"
    description: str = (
        "Write text content to a file. "
        "Input: JSON with keys 'path' (str) and 'content' (str). "
        "Returns the absolute file path."
    )

    def _run(self, json_input: str) -> str:
        data = json.loads(json_input)
        path = Path(data["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data["content"], encoding="utf-8")
        return str(path)


# ── Pipeline ─────────────────────────────────────────────────────────────────

def run_crew(
    image_path: str | Path,
    output_dir: str | Path,
    provider: str = "anthropic",
) -> dict[str, Any]:
    """
    Run the multi-agent CrewAI DXF conversion pipeline.

    Returns:
        dict with keys: dxf, review, crew_result
    """
    image_path = Path(image_path)
    output_dir_p = Path(output_dir)
    output_dir_p.mkdir(parents=True, exist_ok=True)

    # Preprocess image before handing to agents
    preprocessed = output_dir_p / "preprocessed.png"
    preprocess(image_path, preprocessed)

    llm_model = resolve_model(provider)
    writer_tool = DXFWriterTool(output_dir=str(output_dir_p))
    file_tool = WriteFileTool()

    # ── Agents ───────────────────────────────────────────────────────────────

    analyst = Agent(
        role="Engineering Drawing Vision Analyst",
        goal="Extract all geometry from the engineering drawing image with maximum precision.",
        backstory=(
            "Expert in reading metal fabrication drawings. "
            "Accurately identifies part outlines, holes, bend lines, and dimension annotations."
        ),
        llm=llm_model,
        verbose=True,
    )

    builder = Agent(
        role="DXF Building Specialist",
        goal="Convert geometry JSON into a valid, well-structured DXF file using ezdxf.",
        backstory=(
            "Expert in the DXF standard and ezdxf. "
            "Produces clean layered DXF files that open correctly in AutoCAD and SolidWorks."
        ),
        tools=[writer_tool],
        llm=llm_model,
        verbose=True,
    )

    reviewer = Agent(
        role="CAD Quality Reviewer",
        goal="Verify the DXF output and produce a clear review report for the engineer.",
        backstory=(
            "Senior CAD reviewer with 15 years validating metal fabrication drawings "
            "before they reach CNC operators or laser cutters."
        ),
        tools=[file_tool],
        llm=llm_model,
        verbose=True,
    )

    # ── Tasks ─────────────────────────────────────────────────────────────────

    analysis_task = Task(
        description=f"""
        Analyze the preprocessed engineering drawing at: {preprocessed}

        Return a JSON object ONLY (no prose) with this exact structure:
        {{
          "outlines":   [{{"points": [[x, y], ...], "closed": true}}],
          "holes":      [{{"cx": float, "cy": float, "r": float}}],
          "bend_lines": [{{"points": [[x, y], ...]}}],
          "dimensions": [{{"x": float, "y": float, "text": "value"}}],
          "ambiguities": ["describe anything unclear"],
          "confidence":  "high" | "medium" | "low"
        }}

        Use pixel coordinates. Only include clearly visible elements.
        """,
        agent=analyst,
        expected_output="A JSON object describing all detected geometry elements.",
    )

    build_task = Task(
        description=f"""
        Take the geometry JSON from the Vision Analyst and call the write_dxf tool to create the DXF file.
        The tool input must be the raw geometry JSON string.
        Output directory: {output_dir_p}
        Layers to use: CUT (outlines + holes), BEND (fold lines), DIM (dimension text).
        Return the path to the created .dxf file.
        """,
        agent=builder,
        expected_output="The absolute path to the validated drawing.dxf file.",
        context=[analysis_task],
    )

    review_task = Task(
        description=f"""
        Review the DXF conversion and write a review report.

        1. Check the geometry from the Vision Analyst looks complete and consistent.
        2. Confirm layers are correct: CUT / BEND / DIM.
        3. Call write_file with:
           {{"path": "{output_dir_p / 'review.md'}", "content": "<your review markdown>"}}

        Review.md must include:
        - ## Geometry extracted — table: entity type | count | layer
        - ## Confidence — the analyst's overall rating
        - ## ⚠️ Engineer must verify — list all ambiguities (or "None" if clean)

        Return "PASS" or "NEEDS_REVISION: <brief reason>".
        """,
        agent=reviewer,
        expected_output="PASS or NEEDS_REVISION with reason.",
        context=[analysis_task, build_task],
    )

    # ── Crew ─────────────────────────────────────────────────────────────────

    crew = Crew(
        agents=[analyst, builder, reviewer],
        tasks=[analysis_task, build_task, review_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()

    return {
        "dxf":         str(output_dir_p / "drawing.dxf"),
        "review":      str(output_dir_p / "review.md"),
        "crew_result": str(result),
    }
