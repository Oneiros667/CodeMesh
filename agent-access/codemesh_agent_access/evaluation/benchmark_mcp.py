from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from codemesh_agent_access.mcp import build_server


class BenchmarkCallGuard:
    def __init__(self, policy: dict[str, Any], audit_path: Path) -> None:
        self.allowed = set(policy.get("allowed_tools") or [])
        self.max_calls = int(policy.get("max_calls") or 0)
        self.per_tool_limits = {
            str(name): int(limit)
            for name, limit in (policy.get("per_tool_limits") or {}).items()
        }
        self.required_sequence = [
            str(name) for name in policy.get("required_sequence") or []
        ]
        self.audit_path = audit_path
        self.attempts: list[dict[str, Any]] = []
        self.counts: Counter[str] = Counter()

    def __call__(self, name: str, arguments: dict[str, Any]) -> None:
        self.counts[name] += 1
        attempted = len(self.attempts) + 1
        reason: str | None = None
        if name not in self.allowed:
            reason = "tool is not allowed by the benchmark policy"
        elif (
            attempted <= len(self.required_sequence)
            and name != self.required_sequence[attempted - 1]
        ):
            reason = (
                "required tool order violated; expected "
                f"{self.required_sequence[attempted - 1]}"
            )
        elif attempted > self.max_calls:
            reason = "total benchmark tool-call budget exceeded"
        elif self.counts[name] > self.per_tool_limits.get(name, self.max_calls):
            reason = f"per-tool benchmark budget exceeded for {name}"

        entry = {
            "index": attempted,
            "tool": name,
            "argument_names": sorted(arguments),
            "blocked": reason is not None,
            "reason": reason,
        }
        self.attempts.append(entry)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_path.write_text(
            json.dumps({"attempts": self.attempts}, indent=2) + "\n",
            encoding="utf-8",
        )
        if reason is not None:
            raise RuntimeError(reason)


def run() -> None:
    raw_policy = os.environ.get("CODEMESH_BENCHMARK_TOOL_POLICY")
    raw_audit = os.environ.get("CODEMESH_BENCHMARK_TOOL_AUDIT")
    if not raw_policy or not raw_audit:
        raise RuntimeError(
            "CODEMESH_BENCHMARK_TOOL_POLICY and CODEMESH_BENCHMARK_TOOL_AUDIT are required."
        )
    policy = json.loads(raw_policy)
    guard = BenchmarkCallGuard(policy, Path(raw_audit))
    build_server(call_guard=guard).run()


if __name__ == "__main__":
    run()
