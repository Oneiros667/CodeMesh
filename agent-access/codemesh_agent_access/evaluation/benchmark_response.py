from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    stable_key: str | None = None


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    facts: dict[str, Any]
    citations: list[Citation] = Field(min_length=1)


server = FastMCP(
    "codemesh-benchmark-response",
    instructions=(
        "Investigate with the allowed CodeMesh tools. Add exact citations, then "
        "submit the final answer and typed facts exactly once."
    ),
)
_citations: list[Citation] = []
_submitted = False


@server.tool()
def add_benchmark_citation(
    file_path: str,
    start_line: int,
    end_line: int,
    stable_key: str = "",
) -> dict[str, int | bool]:
    """Add an exact repository-relative citation supporting the benchmark answer."""
    citation = Citation(
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        stable_key=stable_key or None,
    )
    _citations.append(citation)
    return {"accepted": True, "citation_count": len(_citations)}


@server.tool()
def submit_benchmark_answer(
    answer: str,
    facts: dict[str, Any],
) -> dict[str, bool]:
    """Submit the final grounded answer and task-specific typed fact values."""
    global _submitted
    if _submitted:
        raise RuntimeError("The benchmark answer has already been submitted.")
    submission = Submission(answer=answer, facts=facts, citations=list(_citations))
    output = os.environ.get("CODEMESH_BENCHMARK_RESPONSE_OUTPUT")
    if not output:
        raise RuntimeError("CODEMESH_BENCHMARK_RESPONSE_OUTPUT is required.")
    Path(output).write_text(
        json.dumps(submission.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    _submitted = True
    return {"accepted": True}


if __name__ == "__main__":
    server.run(transport="stdio")
