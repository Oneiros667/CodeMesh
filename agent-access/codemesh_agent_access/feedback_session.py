from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .binding import RepositoryBinding
from .feedback import OUTBOX_NAME


SESSION_PLAN_SCHEMA_VERSION = "codemesh-development-feedback-session-plan/v1"
SESSION_SCHEMA_VERSION = "codemesh-development-feedback-session/v1"
REVOCATION_SCHEMA_VERSION = "codemesh-development-feedback-revocation/v1"

CLIENT_PROFILE = "development-feedback"
MAINTAINER_PROFILE = "feedback-maintainer"
FEEDBACK_PROFILES = (CLIENT_PROFILE, MAINTAINER_PROFILE)

NORMAL_TOOLS = (
    "codemesh_get_context_package",
    "codemesh_get_repository_status",
    "codemesh_list_repositories",
    "codemesh_get_node",
)
CLIENT_TOOLS = (
    *NORMAL_TOOLS,
    "codemesh_get_feedback_session",
    "codemesh_record_feedback",
)
MAINTAINER_TOOLS = (
    *NORMAL_TOOLS,
    "codemesh_list_feedback",
    "codemesh_get_feedback",
    "codemesh_prepare_feedback_resolution",
)

MAX_SESSION_DURATION = timedelta(days=7)
DEFAULT_MAX_PACKETS = 100
DEFAULT_MAX_REQUESTS_PER_MINUTE = 20
DEFAULT_MAX_TEXT_CHARACTERS = 500
DEFAULT_MAX_PATHS = 32

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9:._/-]{0,159}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionParticipant(_StrictModel):
    project_id: str
    checkout_id: str
    repository_root: str
    reporter_role: str

    @field_validator("project_id", "checkout_id", "reporter_role")
    @classmethod
    def safe_identifier(cls, value: str) -> str:
        text = value.strip()
        if not _IDENTIFIER.fullmatch(text):
            raise ValueError("Session identity contains unsupported characters.")
        return text

    @field_validator("repository_root")
    @classmethod
    def absolute_root(cls, value: str) -> str:
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("Session repository roots must be absolute paths.")
        return str(path.resolve(strict=False))

    def binding(self) -> RepositoryBinding:
        return RepositoryBinding(
            self.project_id,
            self.checkout_id,
            self.repository_root,
        )


class SessionBounds(_StrictModel):
    max_packets: int = Field(default=DEFAULT_MAX_PACKETS, ge=1, le=1000)
    max_requests_per_minute: int = Field(
        default=DEFAULT_MAX_REQUESTS_PER_MINUTE,
        ge=1,
        le=120,
    )
    max_text_characters: int = Field(
        default=DEFAULT_MAX_TEXT_CHARACTERS,
        ge=80,
        le=2000,
    )
    max_paths: int = Field(default=DEFAULT_MAX_PATHS, ge=1, le=64)


class SessionPayload(_StrictModel):
    session_id: str
    created_at: datetime
    expires_at: datetime
    codemesh: SessionParticipant
    clients: list[SessionParticipant] = Field(min_length=1, max_length=32)
    profiles: dict[str, list[str]]
    local_only: Literal[True] = True
    provider_free: Literal[True] = True
    bounds: SessionBounds = Field(default_factory=SessionBounds)

    @field_validator("session_id")
    @classmethod
    def session_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"session-[0-9a-f]{20}", value):
            raise ValueError("Session id has an invalid shape.")
        return value

    @field_validator("created_at", "expires_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Session timestamps must include a timezone.")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_contract(self) -> SessionPayload:
        if self.expires_at <= self.created_at:
            raise ValueError("Session expiry must be after creation.")
        if self.expires_at - self.created_at > MAX_SESSION_DURATION:
            raise ValueError("Session duration exceeds seven days.")
        expected_profiles = {
            CLIENT_PROFILE: list(CLIENT_TOOLS),
            MAINTAINER_PROFILE: list(MAINTAINER_TOOLS),
        }
        if self.profiles != expected_profiles:
            raise ValueError(
                "Session tool profiles do not match the supported contract."
            )
        identities = [(item.project_id, item.checkout_id) for item in self.clients]
        roots = [
            os.path.normcase(os.path.realpath(item.repository_root))
            for item in self.clients
        ]
        if len(identities) != len(set(identities)) or len(roots) != len(set(roots)):
            raise ValueError("Session client participants must be unique.")
        codemesh_root = os.path.normcase(
            os.path.realpath(self.codemesh.repository_root)
        )
        if codemesh_root in roots:
            raise ValueError("The CodeMesh checkout cannot also be a client checkout.")
        return self


class SessionManifest(_StrictModel):
    schema_version: Literal["codemesh-development-feedback-session/v1"] = (
        SESSION_SCHEMA_VERSION
    )
    payload: SessionPayload
    payload_sha256: str

    @field_validator("payload_sha256")
    @classmethod
    def sha256_shape(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("Session payload hash has an invalid shape.")
        return value


class SessionPlan(_StrictModel):
    schema_version: Literal["codemesh-development-feedback-session-plan/v1"] = (
        SESSION_PLAN_SCHEMA_VERSION
    )
    manifest_path: str
    manifest: SessionManifest
    manifest_file_sha256: str
    plan_hash: str

    @field_validator("manifest_path")
    @classmethod
    def absolute_manifest_path(cls, value: str) -> str:
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("Session manifest path must be absolute.")
        return str(path.resolve(strict=False))

    @field_validator("manifest_file_sha256", "plan_hash")
    @classmethod
    def hash_shape(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("Session plan hash has an invalid shape.")
        return value


class SessionRevocation(_StrictModel):
    schema_version: Literal["codemesh-development-feedback-revocation/v1"] = (
        REVOCATION_SCHEMA_VERSION
    )
    session_id: str
    manifest_file_sha256: str
    revoked_at: datetime
    reason: str = Field(min_length=1, max_length=200)
    content_sha256: str

    @field_validator("session_id")
    @classmethod
    def session_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"session-[0-9a-f]{20}", value):
            raise ValueError("Revocation session id has an invalid shape.")
        return value

    @field_validator("manifest_file_sha256", "content_sha256")
    @classmethod
    def hash_shape(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("Revocation hash has an invalid shape.")
        return value

    @field_validator("revoked_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Revocation timestamp must include a timezone.")
        return value.astimezone(UTC)


@dataclass(frozen=True)
class SessionRuntime:
    manifest_path: Path
    manifest_file_sha256: str
    profile: str
    binding: RepositoryBinding
    participant: SessionParticipant
    clock: Callable[[], datetime]

    @property
    def payload(self) -> SessionPayload:
        return load_active_session(
            self.manifest_path,
            self.manifest_file_sha256,
            profile=self.profile,
            binding=self.binding,
            now=self.clock(),
        ).payload

    def assert_active(self) -> SessionPayload:
        return self.payload


def create_session_plan(
    *,
    manifest_path: str | Path,
    codemesh: SessionParticipant,
    clients: list[SessionParticipant],
    expires_at: datetime,
    bounds: SessionBounds | None = None,
    now: datetime | None = None,
) -> SessionPlan:
    created_at = _utc(now or datetime.now(UTC))
    expires_at = _utc(expires_at)
    codemesh = _validated_participant(codemesh, require_ignored_outbox=False)
    clients = [
        _validated_participant(participant, require_ignored_outbox=True)
        for participant in clients
    ]
    clients.sort(
        key=lambda item: (
            item.project_id.casefold(),
            item.checkout_id.casefold(),
            os.path.normcase(item.repository_root),
        )
    )
    selected_bounds = bounds or SessionBounds()
    profiles = {
        CLIENT_PROFILE: list(CLIENT_TOOLS),
        MAINTAINER_PROFILE: list(MAINTAINER_TOOLS),
    }
    core = {
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "codemesh": codemesh.model_dump(mode="json"),
        "clients": [item.model_dump(mode="json") for item in clients],
        "profiles": profiles,
        "bounds": selected_bounds.model_dump(mode="json"),
    }
    session_id = f"session-{_hash_json(core)[:20]}"
    payload = SessionPayload(
        session_id=session_id,
        created_at=created_at,
        expires_at=expires_at,
        codemesh=codemesh,
        clients=clients,
        profiles=profiles,
        bounds=selected_bounds,
    )
    payload_hash = _hash_json(payload.model_dump(mode="json"))
    manifest = SessionManifest(payload=payload, payload_sha256=payload_hash)
    manifest_hash = _hash_bytes(_manifest_bytes(manifest))
    requested_path = Path(manifest_path).expanduser()
    if not requested_path.is_absolute():
        raise ValueError("Session manifest path must be absolute.")
    path = requested_path.resolve(strict=False)
    if not path.parent.is_dir():
        raise ValueError("Session manifest parent directory does not exist.")
    unsigned = {
        "schema_version": SESSION_PLAN_SCHEMA_VERSION,
        "manifest_path": str(path),
        "manifest": manifest.model_dump(mode="json"),
        "manifest_file_sha256": manifest_hash,
    }
    return SessionPlan(**unsigned, plan_hash=_hash_json(unsigned))


def write_session_plan(plan: SessionPlan, path: str | Path) -> None:
    verify_session_plan(plan)
    _exclusive_write(Path(path), _json_bytes(plan.model_dump(mode="json")))


def load_session_plan(path: str | Path) -> SessionPlan:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    plan = SessionPlan.model_validate(payload)
    verify_session_plan(plan)
    return plan


def verify_session_plan(plan: SessionPlan) -> None:
    payload = plan.model_dump(mode="json")
    plan_hash = payload.pop("plan_hash")
    if _hash_json(payload) != plan_hash:
        raise ValueError("Session plan hash does not match its contents.")
    _verify_manifest(plan.manifest)
    if _hash_bytes(_manifest_bytes(plan.manifest)) != plan.manifest_file_sha256:
        raise ValueError("Planned session manifest hash does not match its contents.")


def activate_session(plan: SessionPlan, approved_plan_hash: str) -> Path:
    verify_session_plan(plan)
    if approved_plan_hash != plan.plan_hash:
        raise ValueError("Approved plan hash does not match the reviewed session plan.")
    path = Path(plan.manifest_path)
    if (
        not path.parent.is_dir()
        or path.parent.is_symlink()
        or path.parent.is_junction()
        or path.parent.resolve() != path.parent
    ):
        raise ValueError("Session manifest parent changed after review.")
    _exclusive_write(path, _manifest_bytes(plan.manifest))
    return path


def inspect_session(
    manifest_path: str | Path,
    expected_sha256: str,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    manifest, path = _load_manifest(manifest_path, expected_sha256)
    payload = manifest.payload
    current = _utc(now or datetime.now(UTC))
    status = "expired" if current >= payload.expires_at else "active"
    revocation = _load_revocation(
        path,
        expected_sha256,
        payload.session_id,
        required=False,
    )
    if revocation is not None:
        status = "revoked"
    return {
        "schema_version": "codemesh-development-feedback-session-status/v1",
        "session_id": payload.session_id,
        "status": status,
        "created_at": payload.created_at.isoformat(),
        "expires_at": payload.expires_at.isoformat(),
        "local_only": payload.local_only,
        "provider_free": payload.provider_free,
        "client_count": len(payload.clients),
        "profiles": sorted(payload.profiles),
        "manifest_file_sha256": expected_sha256,
    }


def load_active_session(
    manifest_path: str | Path,
    expected_sha256: str,
    *,
    profile: str,
    binding: RepositoryBinding,
    now: datetime | None = None,
) -> SessionManifest:
    if profile not in FEEDBACK_PROFILES:
        raise ValueError("A development feedback session requires a feedback profile.")
    manifest, path = _load_manifest(manifest_path, expected_sha256)
    payload = manifest.payload
    current = _utc(now or datetime.now(UTC))
    if current >= payload.expires_at:
        raise ValueError("Development feedback session has expired.")
    if (
        _load_revocation(
            path,
            expected_sha256,
            payload.session_id,
            required=False,
        )
        is not None
    ):
        raise ValueError("Development feedback session has been revoked.")
    participants = payload.clients if profile == CLIENT_PROFILE else [payload.codemesh]
    matching = [item for item in participants if _binding_matches(item, binding)]
    if len(matching) != 1:
        raise ValueError(
            "Development feedback session does not authorize this binding."
        )
    return manifest


def create_session_runtime(
    manifest_path: str | Path,
    expected_sha256: str,
    *,
    profile: str,
    binding: RepositoryBinding,
    clock: Callable[[], datetime] | None = None,
) -> SessionRuntime:
    selected_clock = clock or (lambda: datetime.now(UTC))
    manifest = load_active_session(
        manifest_path,
        expected_sha256,
        profile=profile,
        binding=binding,
        now=selected_clock(),
    )
    participants = (
        manifest.payload.clients
        if profile == CLIENT_PROFILE
        else [manifest.payload.codemesh]
    )
    participant = next(item for item in participants if _binding_matches(item, binding))
    return SessionRuntime(
        manifest_path=Path(manifest_path).resolve(strict=True),
        manifest_file_sha256=expected_sha256,
        profile=profile,
        binding=binding,
        participant=participant,
        clock=selected_clock,
    )


def revoke_session(
    manifest_path: str | Path,
    expected_sha256: str,
    *,
    reason: str,
    now: datetime | None = None,
) -> Path:
    manifest, path = _load_manifest(manifest_path, expected_sha256)
    safe_reason = reason.strip()
    if (
        not safe_reason
        or len(safe_reason) > 200
        or any(ord(item) < 32 for item in safe_reason)
    ):
        raise ValueError("Revocation reason must contain 1 to 200 safe characters.")
    draft = SessionRevocation(
        session_id=manifest.payload.session_id,
        manifest_file_sha256=expected_sha256,
        revoked_at=_utc(now or datetime.now(UTC)),
        reason=safe_reason,
        content_sha256="0" * 64,
    )
    unsigned = draft.model_dump(mode="json", exclude={"content_sha256"})
    revocation = draft.model_copy(update={"content_sha256": _hash_json(unsigned)})
    output = revocation_path(path)
    _exclusive_write(output, _json_bytes(revocation.model_dump(mode="json")))
    return output


def revocation_path(manifest_path: str | Path) -> Path:
    path = Path(manifest_path)
    return path.with_name(f"{path.name}.revoked.json")


def _load_manifest(
    manifest_path: str | Path,
    expected_sha256: str,
) -> tuple[SessionManifest, Path]:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("Expected session manifest hash has an invalid shape.")
    requested = Path(manifest_path).expanduser()
    if (
        requested.is_symlink()
        or requested.is_junction()
        or not requested.is_file()
        or requested.stat().st_nlink != 1
    ):
        raise ValueError("Session manifest must be an unlinked local regular file.")
    path = requested.resolve(strict=True)
    if path.stat().st_size > 65_536:
        raise ValueError("Session manifest exceeds the 65,536-byte limit.")
    raw = path.read_bytes()
    if _hash_bytes(raw) != expected_sha256:
        raise ValueError("Session manifest hash does not match the reviewed value.")
    manifest = SessionManifest.model_validate(json.loads(raw))
    _verify_manifest(manifest)
    return manifest, path


def _verify_manifest(manifest: SessionManifest) -> None:
    expected = _hash_json(manifest.payload.model_dump(mode="json"))
    if expected != manifest.payload_sha256:
        raise ValueError("Session payload hash does not match its contents.")


def _load_revocation(
    manifest_path: Path,
    expected_sha256: str,
    expected_session_id: str,
    *,
    required: bool,
) -> SessionRevocation | None:
    path = revocation_path(manifest_path)
    if path.is_symlink() or path.is_junction():
        raise ValueError(
            "Session revocation record must be an unlinked local regular file."
        )
    if not path.exists():
        if required:
            raise ValueError("Session revocation record does not exist.")
        return None
    if not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(
            "Session revocation record must be an unlinked local regular file."
        )
    if path.stat().st_size > 4096:
        raise ValueError("Session revocation record exceeds the 4,096-byte limit.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    revocation = SessionRevocation.model_validate(payload)
    unsigned = revocation.model_dump(mode="json")
    content_hash = unsigned.pop("content_sha256")
    if _hash_json(unsigned) != content_hash:
        raise ValueError("Session revocation hash does not match its contents.")
    if revocation.manifest_file_sha256 != expected_sha256:
        raise ValueError("Session revocation does not match the reviewed manifest.")
    if revocation.session_id != expected_session_id:
        raise ValueError("Session revocation does not match the active session id.")
    return revocation


def _validated_participant(
    participant: SessionParticipant,
    *,
    require_ignored_outbox: bool,
) -> SessionParticipant:
    root = _exact_git_root(participant.repository_root)
    if require_ignored_outbox:
        outbox = root / OUTBOX_NAME
        if outbox.is_symlink() or outbox.is_junction() or outbox.resolve() != outbox:
            raise ValueError(
                "Feedback outbox must be a local directory in the checkout."
            )
        probe = f"{OUTBOX_NAME}/_codemesh-ignore-probe.json"
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", probe],
            cwd=root,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError(f"{outbox} is not ignored.")
    return participant.model_copy(update={"repository_root": str(root)})


def _exact_git_root(value: str | Path) -> Path:
    candidate = Path(value).expanduser().resolve(strict=True)
    if not candidate.is_dir():
        raise ValueError(f"Repository root is not a directory: {candidate}")
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=candidate,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"Session root is not a Git checkout: {candidate}")
    discovered = Path(result.stdout.strip()).resolve()
    if discovered != candidate:
        raise ValueError(
            f"Repository root must be exact: supplied {candidate}, git reports {discovered}."
        )
    return discovered


def _binding_matches(
    participant: SessionParticipant, binding: RepositoryBinding
) -> bool:
    return (
        participant.project_id == binding.project_id
        and participant.checkout_id == binding.checkout_id
        and os.path.normcase(os.path.realpath(participant.repository_root))
        == os.path.normcase(os.path.realpath(binding.repository_root))
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Session timestamps must include a timezone.")
    return value.astimezone(UTC)


def _manifest_bytes(manifest: SessionManifest) -> bytes:
    return _json_bytes(manifest.model_dump(mode="json"))


def _json_bytes(value: dict[str, object]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _hash_json(value: dict[str, object]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _exclusive_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise
