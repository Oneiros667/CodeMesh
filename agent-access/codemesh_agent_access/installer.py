from __future__ import annotations

from dataclasses import asdict, dataclass
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from .binding import RepositoryBinding
from .mcp import DEFAULT_TOOL_PROFILE, tool_manifest


SCHEMA_VERSION = "codemesh-installation-plan-v1"
CONFIG_START = "# codemesh:config:start"
CONFIG_END = "# codemesh:config:end"
ONBOARDING_START = "<!-- codemesh:onboarding:start -->"
ONBOARDING_END = "<!-- codemesh:onboarding:end -->"

_FORWARDED_ENVIRONMENT_NAMES = [
    "CODEMESH_NEO4J_URI",
    "CODEMESH_NEO4J_AUTH",
    "CODEMESH_NEO4J_USER",
    "CODEMESH_NEO4J_PASSWORD",
    "CODEMESH_NEO4J_DATABASE",
    "CODEMESH_MONGO_URI",
    "CODEMESH_MONGO_DATABASE",
    "CODEMESH_MONGO_CONTENT_COLLECTION",
    "CODEMESH_MONGO_REPOSITORIES_COLLECTION",
    "CODEMESH_MONGO_INGESTION_RUNS_COLLECTION",
    "CODEMESH_MONGO_NODE_SUMMARIES_COLLECTION",
    "CODEMESH_QDRANT_URL",
    "CODEMESH_QDRANT_COLLECTION",
]


@dataclass(frozen=True)
class PlannedFile:
    path: str
    previous_sha256: str | None
    new_sha256: str
    content: str
    diff: str


@dataclass(frozen=True)
class InstallationPlan:
    schema_version: str
    target_root: str
    codemesh_root: str
    server_name: str
    profile: str
    binding: dict[str, str | None]
    launch: dict[str, Any]
    files: tuple[PlannedFile, ...]
    plan_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_installation_plan(
    target_root: str | Path,
    codemesh_root: str | Path,
    binding: RepositoryBinding,
    *,
    server_name: str = "codemesh",
    profile: str = DEFAULT_TOOL_PROFILE,
    include_onboarding: bool = True,
) -> InstallationPlan:
    target = Path(target_root).expanduser().resolve(strict=True)
    codemesh = Path(codemesh_root).expanduser().resolve(strict=True)
    agent_access = codemesh / "agent-access"
    if not (agent_access / "pyproject.toml").is_file():
        raise ValueError(f"CodeMesh Agent Access was not found under '{agent_access}'.")
    if Path(binding.repository_root) != target:
        raise ValueError(
            "Installation target must match the configured repository binding root."
        )
    if not re.fullmatch(r"[A-Za-z0-9_-]+", server_name):
        raise ValueError(
            "MCP server name may contain only letters, numbers, underscores, and hyphens."
        )

    launch = {
        "command": "uv",
        "args": [
            "run",
            "--directory",
            str(agent_access),
            "python",
            "-m",
            "codemesh_agent_access",
            "mcp",
            "--profile",
            profile,
            "--project-id",
            binding.project_id,
            "--checkout-id",
            binding.checkout_id,
            "--repository-root",
            binding.repository_root,
            *(
                ["--source-view-hash", binding.source_view_hash]
                if binding.source_view_hash
                else []
            ),
        ],
        "cwd": str(agent_access),
        "profile": profile,
        "expected_tools": [
            item["name"] for item in tool_manifest(profile=profile)["tools"]
        ],
    }
    config_path = target / ".codex" / "config.toml"
    agents_path = target / "AGENTS.md"
    config_block = _config_block(server_name, launch)
    onboarding_block = _onboarding_block(server_name)
    planned_files = [
        _plan_file(
            config_path,
            _updated_managed_file(
                config_path,
                CONFIG_START,
                CONFIG_END,
                config_block,
                unmanaged_conflict=f"[mcp_servers.{server_name}]",
            ),
            target,
        )
    ]
    if include_onboarding:
        planned_files.append(
            _plan_file(
                agents_path,
                _updated_managed_file(
                    agents_path,
                    ONBOARDING_START,
                    ONBOARDING_END,
                    onboarding_block,
                ),
                target,
            )
        )
    files = tuple(planned_files)
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "target_root": str(target),
        "codemesh_root": str(codemesh),
        "server_name": server_name,
        "profile": profile,
        "binding": binding.as_dict(),
        "launch": launch,
        "files": [asdict(item) for item in files],
    }
    return InstallationPlan(
        schema_version=SCHEMA_VERSION,
        target_root=str(target),
        codemesh_root=str(codemesh),
        server_name=server_name,
        profile=profile,
        binding=binding.as_dict(),
        launch=launch,
        files=files,
        plan_hash=_hash_json(unsigned),
    )


def load_installation_plan(path: str | Path) -> InstallationPlan:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported CodeMesh installation-plan schema.")
    files = tuple(PlannedFile(**item) for item in payload.get("files", []))
    plan = InstallationPlan(
        schema_version=str(payload["schema_version"]),
        target_root=str(payload["target_root"]),
        codemesh_root=str(payload["codemesh_root"]),
        server_name=str(payload["server_name"]),
        profile=str(payload["profile"]),
        binding=dict(payload["binding"]),
        launch=dict(payload["launch"]),
        files=files,
        plan_hash=str(payload["plan_hash"]),
    )
    verify_installation_plan(plan)
    return plan


def write_installation_plan(plan: InstallationPlan, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(
        output,
        json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n",
    )


def apply_installation_plan(
    plan: InstallationPlan,
    approved_plan_hash: str,
) -> list[str]:
    verify_installation_plan(plan)
    if approved_plan_hash != plan.plan_hash:
        raise ValueError(
            "Approved plan hash does not match the reviewed installation plan."
        )
    target = Path(plan.target_root).resolve(strict=True)
    pending: list[tuple[Path, PlannedFile]] = []
    for item in plan.files:
        path = (target / item.path).resolve(strict=False)
        if target != path and target not in path.parents:
            raise ValueError(f"Installation path escapes target root: {item.path}")
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        current_hash = _hash_text(current) if path.exists() else None
        if current_hash != item.previous_sha256:
            raise ValueError(f"Installation target changed after review: {item.path}.")
        if _hash_text(item.content) != item.new_sha256:
            raise ValueError(f"Planned content hash is invalid: {item.path}.")
        pending.append((path, item))

    changed: list[str] = []
    for path, item in pending:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current == item.content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, item.content)
        changed.append(item.path)
    return changed


def verify_plan_applied(plan: InstallationPlan) -> None:
    verify_installation_plan(plan)
    target = Path(plan.target_root).resolve(strict=True)
    for item in plan.files:
        path = (target / item.path).resolve(strict=False)
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if _hash_text(current) != item.new_sha256:
            raise ValueError(
                f"Installed file does not match the reviewed plan: {item.path}."
            )


def codex_mcp_overrides(
    plan: InstallationPlan,
    *,
    approve_tools: bool = False,
) -> tuple[str, ...]:
    """Render the reviewed launch as isolated Codex CLI configuration overrides."""
    verify_installation_plan(plan)
    launch = plan.launch
    if launch.get("profile") != plan.profile:
        raise ValueError("Installation launch profile does not match the plan profile.")
    expected_tools = launch.get("expected_tools")
    if not isinstance(expected_tools, list) or not expected_tools:
        raise ValueError("Installation plan has no expected MCP tool surface.")
    command = launch.get("command")
    args = launch.get("args")
    cwd = launch.get("cwd")
    if not isinstance(command, str) or not command:
        raise ValueError("Installation plan has no MCP launch command.")
    if not isinstance(args, list) or not all(isinstance(value, str) for value in args):
        raise ValueError("Installation plan has invalid MCP launch arguments.")
    if not isinstance(cwd, str) or not cwd:
        raise ValueError("Installation plan has no MCP launch working directory.")

    prefix = f"mcp_servers.{plan.server_name}"
    overrides = [
        f"{prefix}.command={json.dumps(command)}",
        f"{prefix}.args={json.dumps(args)}",
        f"{prefix}.cwd={json.dumps(cwd)}",
        f"{prefix}.required=true",
        f"{prefix}.startup_timeout_sec=30",
        f"{prefix}.tool_timeout_sec=60",
        f"{prefix}.enabled_tools={json.dumps(expected_tools)}",
        f"{prefix}.env_vars={json.dumps(_FORWARDED_ENVIRONMENT_NAMES)}",
        f'{prefix}.env={{ CODEMESH_MODEL_PROVIDER = "none" }}',
    ]
    if approve_tools:
        overrides.append(f'{prefix}.default_tools_approval_mode="approve"')
    return tuple(overrides)


def verify_installation_plan(plan: InstallationPlan) -> None:
    if plan.plan_hash != _plan_hash(plan):
        raise ValueError("Installation plan hash does not match its contents.")


def _config_block(server_name: str, launch: dict[str, Any]) -> str:
    enabled_tools = launch["expected_tools"]
    env_names = ", ".join(json.dumps(name) for name in _FORWARDED_ENVIRONMENT_NAMES)
    return "\n".join(
        [
            CONFIG_START,
            f"[mcp_servers.{server_name}]",
            f"command = {json.dumps(launch['command'])}",
            f"args = {_toml_array(launch['args'])}",
            f"cwd = {json.dumps(launch['cwd'])}",
            "required = true",
            "startup_timeout_sec = 30",
            "tool_timeout_sec = 60",
            f"enabled_tools = {_toml_array(enabled_tools)}",
            f"env_vars = [{env_names}]",
            'env = { CODEMESH_MODEL_PROVIDER = "none" }',
            CONFIG_END,
        ]
    )


def _onboarding_block(server_name: str) -> str:
    return "\n".join(
        [
            ONBOARDING_START,
            "## CodeMesh repository context",
            "",
            f"The `{server_name}` MCP server is bound to this exact checkout.",
            "For implementation discovery, likely change-impact analysis, and",
            "validation selection:",
            "",
            "1. Start with one `codemesh_get_context_package` call using a concise",
            "   task-shaped query and default limits, with",
            '   `output_format = "agent"`; omit `repository_id` so the server uses',
            "   its checkout binding. If the package covers every required facet,",
            "   stop retrieving. Only issue one focused follow-up when a specific",
            "   implementation or test facet remains unresolved. Use at most three",
            "   packages for the task and avoid overlapping queries. The package",
            "   validates the exact",
            "   binding and freshness before search; it fails closed when they are not accepted.",
            "2. If the package rejects the binding or freshness, stop using CodeMesh",
            "   and fall back to direct source inspection. Use",
            "   `codemesh_get_repository_status` only for explicit diagnostics.",
            "3. Verify consequential findings against returned source spans with",
            "   targeted reads. Relationships are navigation evidence, not runtime proof.",
            "4. Record missing, stale, incorrect, or unhelpful results through the",
            "   repository's CodeMesh feedback workflow when it is available.",
            ONBOARDING_END,
        ]
    )


def _updated_managed_file(
    path: Path,
    start: str,
    end: str,
    block: str,
    *,
    unmanaged_conflict: str | None = None,
) -> str:
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    start_count = current.count(start)
    end_count = current.count(end)
    if start_count != end_count or start_count > 1:
        raise ValueError(f"Managed CodeMesh markers are malformed in '{path}'.")
    if start_count == 0:
        if unmanaged_conflict and unmanaged_conflict in current:
            raise ValueError(
                f"Unmanaged CodeMesh MCP configuration already exists in '{path}'."
            )
        prefix = current.rstrip()
        return f"{prefix}\n\n{block}\n" if prefix else f"{block}\n"

    before, remainder = current.split(start, 1)
    _old, after = remainder.split(end, 1)
    return f"{before}{block}{after}".rstrip() + "\n"


def _plan_file(path: Path, content: str, target: Path) -> PlannedFile:
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    relative = path.relative_to(target).as_posix()
    diff = "".join(
        difflib.unified_diff(
            previous.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
        )
    )
    return PlannedFile(
        path=relative,
        previous_sha256=_hash_text(previous) if path.exists() else None,
        new_sha256=_hash_text(content),
        content=content,
        diff=diff,
    )


def _plan_hash(plan: InstallationPlan) -> str:
    payload = plan.to_dict()
    payload.pop("plan_hash", None)
    return _hash_json(payload)


def _hash_json(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(json.dumps(value) for value in values) + "]"


def _atomic_write(path: Path, content: str) -> None:
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
