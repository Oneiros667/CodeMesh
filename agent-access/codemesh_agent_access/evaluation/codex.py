from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, Mapping, Protocol


REPORTED_TOKEN_ACCOUNTING_ID = "input-output-reasoning-v1"
REPORTED_TOKEN_ACCOUNTING_DESCRIPTION = (
    "input_tokens + output_tokens + reasoning_output_tokens; "
    "cached_input_tokens is a subset of input_tokens and is not added again"
)


_SECRET_PATTERNS = [
    re.compile(r"(?i)(token|password|secret|api[_-]?key)(\s*[:=]\s*)[^\s,;\"']+"),
    re.compile(
        r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.S
    ),
]


@dataclass(frozen=True)
class AgentRunRequest:
    prompt: str
    cwd: Path
    condition: Literal["control", "treatment"]
    model: str
    reasoning_effort: str
    sandbox: Literal["read-only", "workspace-write"]
    timeout_seconds: int
    mcp_cwd: Path
    local_provider: Literal["lmstudio", "ollama"] | None = None
    output_schema: Path | None = None
    keep_raw_traces: bool = False
    mcp_config: tuple[str, ...] | None = None
    max_reported_tokens: int | None = None


@dataclass
class AgentRunResult:
    completed: bool
    exit_code: int
    duration_ms: float
    final_message: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    mcp_calls: list[str] = field(default_factory=list)
    mcp_call_attempts: list[str] = field(default_factory=list)
    mcp_failed_calls: list[str] = field(default_factory=list)
    command_count: int = 0
    commands: list[str] = field(default_factory=list)
    file_change_count: int = 0
    failures: list[str] = field(default_factory=list)
    raw_events: list[dict[str, Any]] = field(default_factory=list)
    hard_cap_ledger: dict[str, Any] | None = None


@dataclass(frozen=True)
class AgentRunnerCapabilities:
    hard_reported_token_cap: bool
    reported_token_accounting: str | None = None
    runner_id: str | None = None


class AgentRunner(Protocol):
    @property
    def capabilities(self) -> AgentRunnerCapabilities: ...

    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...


class CodexRunner:
    def __init__(
        self,
        executable: str = "codex",
        *,
        supports_ignore_user_config: bool | None = None,
        config_overrides: tuple[str, ...] = (),
        environment_overrides: Mapping[str, str] | None = None,
    ) -> None:
        self.executable = executable
        self._supports_ignore_user_config = supports_ignore_user_config
        self._config_overrides = config_overrides
        self._environment_overrides = dict(environment_overrides or {})

    @property
    def capabilities(self) -> AgentRunnerCapabilities:
        # Codex JSONL reports usage only after a completed turn. The executable
        # currently exposes no per-invocation hard limit using this accounting,
        # so post-run observation must not be presented as enforcement.
        return AgentRunnerCapabilities(
            hard_reported_token_cap=False,
            reported_token_accounting=REPORTED_TOKEN_ACCOUNTING_ID,
            runner_id="codex",
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        supports_ignore_user_config = self._detect_ignore_user_config()
        arguments = self._arguments(
            request, supports_ignore_user_config=supports_ignore_user_config
        )
        isolated_home: tempfile.TemporaryDirectory[str] | None = None
        environment: dict[str, str] | None = None
        if self._environment_overrides:
            environment = os.environ.copy()
            environment.update(self._environment_overrides)
        if not supports_ignore_user_config:
            if request.local_provider is None:
                raise RuntimeError(
                    "The selected Codex executable lacks --ignore-user-config; "
                    "legacy isolation is supported only with a local provider."
                )
            isolated_home = tempfile.TemporaryDirectory(prefix="codemesh-codex-home-")
            environment = environment or os.environ.copy()
            environment["CODEX_HOME"] = isolated_home.name
        started = perf_counter()
        try:
            process = await asyncio.create_subprocess_exec(
                self.executable,
                *arguments,
                cwd=request.cwd,
                env=environment,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name != "nt",
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=request.timeout_seconds
                )
            except TimeoutError:
                _kill_process(process)
                stdout, stderr = await process.communicate()
                parsed = parse_codex_jsonl(stdout.decode("utf-8", errors="replace"))
                parsed.completed = False
                parsed.failures.append(
                    f"Codex timed out after {request.timeout_seconds} seconds."
                )
            else:
                parsed = parse_codex_jsonl(stdout.decode("utf-8", errors="replace"))
        finally:
            if isolated_home is not None:
                isolated_home.cleanup()

        parsed.exit_code = process.returncode if process.returncode is not None else -1
        parsed.duration_ms = round((perf_counter() - started) * 1000, 3)
        if parsed.exit_code != 0:
            error = sanitize_text(stderr.decode("utf-8", errors="replace"))[-2000:]
            parsed.failures.append(
                f"Codex exited with {parsed.exit_code}: {error}".strip()
            )
            parsed.completed = False
        if not request.keep_raw_traces:
            parsed.raw_events = []
        return parsed

    def _arguments(
        self,
        request: AgentRunRequest,
        *,
        supports_ignore_user_config: bool | None = None,
    ) -> list[str]:
        mcp_config = (
            list(request.mcp_config)
            if request.mcp_config is not None
            else _codemesh_mcp_config(request.mcp_cwd)
            if request.condition == "treatment"
            else ["mcp_servers={}"]
        )
        arguments = [
            "--ask-for-approval",
            "never",
            "exec",
            "--ephemeral",
            "--json",
            "--model",
            request.model,
            "--sandbox",
            request.sandbox,
            "--cd",
            str(request.cwd),
            "-c",
            f"model_reasoning_effort={json.dumps(request.reasoning_effort)}",
        ]
        if supports_ignore_user_config is not False:
            arguments.insert(3, "--ignore-user-config")
        for override in mcp_config:
            arguments.extend(["-c", override])
        for override in self._config_overrides:
            arguments.extend(["-c", override])
        if request.local_provider is not None:
            arguments.extend(["--oss", "--local-provider", request.local_provider])
        if request.output_schema is not None:
            arguments.extend(["--output-schema", str(request.output_schema)])
        arguments.append(request.prompt)
        return arguments

    def _detect_ignore_user_config(self) -> bool:
        if self._supports_ignore_user_config is None:
            result = subprocess.run(
                [self.executable, "exec", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self._supports_ignore_user_config = (
                result.returncode == 0 and "--ignore-user-config" in result.stdout
            )
        return self._supports_ignore_user_config


def parse_codex_jsonl(text: str) -> AgentRunResult:
    result = AgentRunResult(completed=False, exit_code=0, duration_ms=0)
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            result.failures.append("Codex emitted a malformed JSONL event.")
            continue
        if not isinstance(event, dict):
            continue
        result.raw_events.append(event)
        event_type = str(event.get("type") or "")
        if event_type == "turn.completed":
            result.completed = True
            usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
            for key in (
                "input_tokens",
                "cached_input_tokens",
                "output_tokens",
                "reasoning_output_tokens",
            ):
                result.usage[key] = _integer(usage.get(key))
        elif event_type in {"turn.failed", "error"}:
            result.completed = False
            message = event.get("message") or event.get("error") or event_type
            result.failures.append(sanitize_text(str(message)))

        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        item_type = str(item.get("type") or "")
        if event_type == "item.completed" and item_type == "agent_message":
            result.final_message = str(item.get("text") or "")
        if (
            item_type in {"command_execution", "command"}
            and event_type == "item.completed"
        ):
            result.command_count += 1
            command = item.get("command") or ""
            if isinstance(command, list):
                command = " ".join(str(part) for part in command)
            if command:
                result.commands.append(str(command))
        if (
            item_type in {"file_change", "file_changes"}
            and event_type == "item.completed"
        ):
            result.file_change_count += 1
        if item_type in {"mcp_tool_call", "mcp_call"} and event_type in {
            "item.started",
            "item.completed",
        }:
            server = str(item.get("server") or item.get("server_name") or "")
            tool = str(
                item.get("tool") or item.get("tool_name") or item.get("name") or ""
            )
            call = f"{server}.{tool}".strip(".")
            if call and event_type == "item.started":
                result.mcp_call_attempts.append(call)
            if call and call not in result.mcp_calls:
                result.mcp_calls.append(call)
            if (
                call
                and event_type == "item.completed"
                and (item.get("error") or item.get("status") in {"failed", "error"})
                and call not in result.mcp_failed_calls
            ):
                result.mcp_failed_calls.append(call)
    return result


def sanitize_text(value: str) -> str:
    sanitized = value
    for pattern in _SECRET_PATTERNS:
        if "PRIVATE KEY" in pattern.pattern:
            sanitized = pattern.sub("[REDACTED PRIVATE KEY]", sanitized)
        else:
            sanitized = pattern.sub(
                lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", sanitized
            )
    return sanitized


def count_reported_tokens(usage: Mapping[str, Any]) -> int:
    """Count runner-reported tokens without double-counting cached input."""
    required_fields = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
    )
    missing = [key for key in required_fields if key not in usage]
    if missing:
        raise ValueError(
            "Reported usage is missing required token fields: " + ", ".join(missing)
        )
    counts = {key: _reported_token_integer(usage[key], key) for key in required_fields}
    if counts["cached_input_tokens"] > counts["input_tokens"]:
        raise ValueError(
            "cached_input_tokens cannot exceed input_tokens in reported usage."
        )
    return (
        counts["input_tokens"]
        + counts["output_tokens"]
        + counts["reasoning_output_tokens"]
    )


def _codemesh_mcp_config(cwd: Path) -> list[str]:
    enabled_tools = [
        "codemesh_status",
        "codemesh_get_tool_guidance",
        "codemesh_search_context",
        "codemesh_get_context_package",
        "codemesh_search_symbols",
        "codemesh_get_node",
        "codemesh_get_neighbors",
        "codemesh_list_repositories",
        "codemesh_get_repository",
        "codemesh_get_repository_status",
        "codemesh_get_summary_coverage",
        "codemesh_list_ingestion_runs",
    ]
    prefix = "mcp_servers.codemesh"
    return [
        f"{prefix}.command={json.dumps('uv')}",
        f"{prefix}.args={json.dumps(['run', 'python', '-m', 'codemesh_agent_access', 'mcp', '--profile', 'diagnostic'])}",
        f"{prefix}.cwd={json.dumps(str(cwd))}",
        f"{prefix}.required=true",
        f"{prefix}.default_tools_approval_mode={json.dumps('approve')}",
        f"{prefix}.startup_timeout_sec=30",
        f"{prefix}.tool_timeout_sec=60",
        f"{prefix}.enabled_tools={json.dumps(enabled_tools)}",
    ]


def _kill_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
    process.kill()


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _reported_token_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f"{field_name} must be a non-negative integer in reported usage."
        )
    return value
