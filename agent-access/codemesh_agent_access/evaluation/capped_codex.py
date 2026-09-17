from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import socket
import subprocess
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Mapping

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .codex import (
    REPORTED_TOKEN_ACCOUNTING_ID,
    AgentRunRequest,
    AgentRunResult,
    AgentRunnerCapabilities,
    CodexRunner,
    count_reported_tokens,
)


_INPUT_TOKEN_FIELDS = {
    "conversation",
    "input",
    "instructions",
    "model",
    "parallel_tool_calls",
    "personality",
    "previous_response_id",
    "reasoning",
    "text",
    "tool_choice",
    "tools",
    "truncation",
}
_ALLOWED_RESPONSE_FIELDS = _INPUT_TOKEN_FIELDS | {
    "background",
    "client_metadata",
    "context_management",
    "include",
    "max_output_tokens",
    "max_tool_calls",
    "metadata",
    "prompt_cache_key",
    "prompt_cache_options",
    "prompt_cache_retention",
    "safety_identifier",
    "service_tier",
    "store",
    "stream",
    "stream_options",
    "temperature",
    "top_logprobs",
    "top_p",
    "user",
}
_ALLOWED_LOCAL_TOOL_TYPES = {"custom", "function"}
_MAX_GENERATED_TOKENS_PER_REQUEST = 128_000
_USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


class CappedProxyError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Reservation:
    sequence: int
    input_tokens: int
    reserved_tokens: int


class HardCapLedger:
    def __init__(self, ceiling: int) -> None:
        if isinstance(ceiling, bool) or not isinstance(ceiling, int) or ceiling < 1:
            raise ValueError("Hard-cap ceiling must be a positive integer.")
        self.ceiling = ceiling
        self.committed_tokens = 0
        self.reported_usage = {field: 0 for field in _USAGE_FIELDS}
        self.request_count = 0
        self.completed_request_count = 0
        self.failures: list[str] = []

    def reserve(
        self, input_tokens: int, requested_output_tokens: int | None
    ) -> tuple[_Reservation, int]:
        if self.failures:
            raise CappedProxyError("The hard-cap ledger is already failed closed.")
        if isinstance(input_tokens, bool) or input_tokens < 0:
            raise CappedProxyError("Input-token counting returned an invalid value.")
        if requested_output_tokens is not None and (
            isinstance(requested_output_tokens, bool)
            or not isinstance(requested_output_tokens, int)
            or requested_output_tokens < 1
        ):
            raise CappedProxyError(
                "The Responses request supplied an invalid max_output_tokens value."
            )
        remaining = self.ceiling - self.committed_tokens
        output_allowance = min(
            (remaining - input_tokens) // 2,
            _MAX_GENERATED_TOKENS_PER_REQUEST,
        )
        if output_allowance < 1:
            raise CappedProxyError(
                "Insufficient remaining hard-cap allowance for the counted input and "
                "one generated token under output-plus-reasoning accounting."
            )
        if requested_output_tokens is not None:
            output_allowance = min(output_allowance, requested_output_tokens)
        reservation = _Reservation(
            sequence=self.request_count + 1,
            input_tokens=input_tokens,
            reserved_tokens=input_tokens + (2 * output_allowance),
        )
        self.request_count += 1
        self.committed_tokens += reservation.reserved_tokens
        return reservation, output_allowance

    def settle(self, reservation: _Reservation, usage: Mapping[str, Any]) -> None:
        normalized = normalize_response_usage(usage)
        if normalized["input_tokens"] != reservation.input_tokens:
            raise CappedProxyError(
                "Response usage disagreed with the preflight input-token count."
            )
        reported_tokens = count_reported_tokens(normalized)
        if reported_tokens > reservation.reserved_tokens:
            raise CappedProxyError("Response usage exceeded its hard-cap reservation.")
        self.committed_tokens -= reservation.reserved_tokens - reported_tokens
        for field in _USAGE_FIELDS:
            self.reported_usage[field] += normalized[field]
        self.completed_request_count += 1

    def fail(self, message: str) -> None:
        if message not in self.failures:
            self.failures.append(message)

    def snapshot(self) -> dict[str, Any]:
        reported_tokens = count_reported_tokens(self.reported_usage)
        return {
            "accounting": REPORTED_TOKEN_ACCOUNTING_ID,
            "ceiling": self.ceiling,
            "committed_tokens": self.committed_tokens,
            "reported_tokens": reported_tokens,
            "retained_reservation_tokens": self.committed_tokens - reported_tokens,
            "remaining_tokens": self.ceiling - self.committed_tokens,
            "request_count": self.request_count,
            "completed_request_count": self.completed_request_count,
            "usage": dict(self.reported_usage),
            "request_max_retries": 0,
            "stream_max_retries": 0,
            "failures": list(self.failures),
            "complete": (
                self.request_count > 0
                and self.request_count == self.completed_request_count
                and not self.failures
            ),
        }


def normalize_response_usage(usage: Mapping[str, Any]) -> dict[str, int]:
    if not isinstance(usage, Mapping):
        raise CappedProxyError("A completed Responses call omitted usage accounting.")
    input_tokens = _non_negative_integer(usage.get("input_tokens"), "input_tokens")
    combined_output_tokens = _non_negative_integer(
        usage.get("output_tokens"), "output_tokens"
    )
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    if not isinstance(input_details, Mapping) or not isinstance(
        output_details, Mapping
    ):
        raise CappedProxyError("Responses usage details had an invalid shape.")
    cached_input_tokens = _optional_non_negative_integer(
        input_details.get("cached_tokens"), "cached_tokens"
    )
    reasoning_output_tokens = _optional_non_negative_integer(
        output_details.get("reasoning_tokens"), "reasoning_tokens"
    )
    if cached_input_tokens > input_tokens:
        raise CappedProxyError("Cached input usage exceeded total input usage.")
    if reasoning_output_tokens > combined_output_tokens:
        raise CappedProxyError("Reasoning usage exceeded total generated usage.")
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": combined_output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
    }


class _SseUsageObserver:
    def __init__(self) -> None:
        self._buffer = b""
        self.terminal_usage: Mapping[str, Any] | None = None

    def feed(self, chunk: bytes) -> None:
        self._buffer += chunk
        normalized = self._buffer.replace(b"\r\n", b"\n")
        frames = normalized.split(b"\n\n")
        self._buffer = frames.pop()
        for frame in frames:
            data = b"\n".join(
                line[5:].lstrip()
                for line in frame.splitlines()
                if line.startswith(b"data:")
            )
            if not data or data == b"[DONE]":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("type") != "response.completed":
                continue
            response = event.get("response")
            if isinstance(response, dict):
                usage = response.get("usage")
                if isinstance(usage, Mapping):
                    self.terminal_usage = usage


class CappedResponsesProxy:
    def __init__(
        self,
        *,
        ceiling: int,
        local_token: str,
        upstream_api_key: str,
        upstream_base_url: str = "https://api.openai.com/v1",
        upstream_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.ledger = HardCapLedger(ceiling)
        self._local_token = local_token
        self._upstream_api_key = upstream_api_key
        self._upstream_base_url = upstream_base_url.rstrip("/")
        self._request_lock = asyncio.Lock()
        self._seen_request_digests: set[str] = set()
        self._owns_client = upstream_client is None
        self._client = upstream_client or httpx.AsyncClient(
            timeout=None,
            transport=httpx.AsyncHTTPTransport(retries=0),
        )
        self.app = Starlette(
            routes=[
                Route("/v1/responses", self._responses, methods=["POST"]),
                Route("/v1/models", self._models, methods=["GET"]),
                Route(
                    "/{path:path}",
                    self._unsupported,
                    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                ),
            ]
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @asynccontextmanager
    async def serve(self) -> AsyncIterator[str]:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = int(listener.getsockname()[1])
        config = uvicorn.Config(
            self.app,
            host="127.0.0.1",
            port=port,
            access_log=False,
            log_config=None,
            lifespan="off",
            server_header=False,
        )
        server = uvicorn.Server(config)
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            await asyncio.wait_for(_wait_for_server(server, task), timeout=5)
            yield f"http://127.0.0.1:{port}/v1"
        finally:
            server.should_exit = True
            try:
                await asyncio.wait_for(task, timeout=5)
            except TimeoutError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            listener.close()
            await self.close()

    async def _responses(self, request: Request) -> Response:
        if not _authorized(request, self._local_token):
            return self._reject("Unauthorized loopback proxy request.", 401)
        retry_count = request.headers.get("x-stainless-retry-count", "0")
        if retry_count not in {"", "0"}:
            return self._reject("Unrecognized provider retry activity was rejected.")
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._reject("Responses request body was not valid JSON.")
        if not isinstance(body, dict):
            return self._reject("Responses request body must be a JSON object.")
        invalid = _validate_response_request(body)
        if invalid:
            return self._reject(invalid)
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        async with self._request_lock:
            if digest in self._seen_request_digests:
                return self._reject(
                    "A duplicate Responses request was rejected as retry activity."
                )
            self._seen_request_digests.add(digest)
            try:
                input_tokens = await self._count_input_tokens(body)
                reservation, output_allowance = self.ledger.reserve(
                    input_tokens, body.get("max_output_tokens")
                )
            except CappedProxyError as exc:
                return self._reject(str(exc))

        forwarded = dict(body)
        forwarded["max_output_tokens"] = output_allowance
        try:
            upstream = await self._client.send(
                self._client.build_request(
                    "POST",
                    f"{self._upstream_base_url}/responses",
                    headers=self._upstream_headers(),
                    json=forwarded,
                ),
                stream=True,
            )
        except httpx.HTTPError:
            self.ledger.fail(
                "The upstream Responses request failed after reservation; the "
                "reservation was retained."
            )
            return JSONResponse({"error": {"message": "Capped upstream failure."}}, 502)

        if upstream.status_code >= 400:
            await upstream.aread()
            await upstream.aclose()
            self.ledger.fail(
                "The upstream Responses request was rejected after reservation; the "
                "reservation was retained."
            )
            return JSONResponse(
                {"error": {"message": "Capped upstream request was rejected."}},
                status_code=upstream.status_code,
            )

        if body.get("stream") is True:
            return StreamingResponse(
                self._stream_response(upstream, reservation),
                status_code=upstream.status_code,
                media_type="text/event-stream",
            )

        content = await upstream.aread()
        await upstream.aclose()
        try:
            payload = json.loads(content)
            if not isinstance(payload, dict) or payload.get("status") != "completed":
                raise CappedProxyError(
                    "The non-streaming Responses call did not complete normally."
                )
            self.ledger.settle(reservation, payload.get("usage"))
        except (json.JSONDecodeError, CappedProxyError) as exc:
            self.ledger.fail(f"{exc} The reservation was retained.")
        return Response(
            content=content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )

    async def _stream_response(
        self, upstream: httpx.Response, reservation: _Reservation
    ) -> AsyncIterator[bytes]:
        observer = _SseUsageObserver()
        settled = False
        try:
            async for chunk in upstream.aiter_raw():
                observer.feed(chunk)
                if observer.terminal_usage is not None and not settled:
                    self.ledger.settle(reservation, observer.terminal_usage)
                    settled = True
                yield chunk
            if not settled:
                raise CappedProxyError(
                    "The Responses stream ended without completed usage."
                )
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            message = (
                str(exc)
                if isinstance(exc, CappedProxyError)
                else "The Responses stream was interrupted."
            )
            self.ledger.fail(f"{message} The reservation was retained.")
            if not isinstance(exc, CappedProxyError):
                raise
        finally:
            await upstream.aclose()
            if (
                not settled
                and observer.terminal_usage is None
                and not self.ledger.failures
            ):
                self.ledger.fail(
                    "The Responses stream ended without completed usage; the "
                    "reservation was retained."
                )

    async def _count_input_tokens(self, body: Mapping[str, Any]) -> int:
        count_body = {key: body[key] for key in _INPUT_TOKEN_FIELDS if key in body}
        try:
            response = await self._client.post(
                f"{self._upstream_base_url}/responses/input_tokens",
                headers=self._upstream_headers(),
                json=count_body,
            )
        except httpx.HTTPError as exc:
            raise CappedProxyError("Input-token counting failed closed.") from exc
        if response.status_code >= 400:
            raise CappedProxyError("Input-token counting was rejected upstream.")
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise CappedProxyError(
                "Input-token counting returned invalid JSON."
            ) from exc
        if not isinstance(payload, dict):
            raise CappedProxyError("Input-token counting returned an invalid payload.")
        return _non_negative_integer(payload.get("input_tokens"), "input_tokens")

    def _upstream_headers(self) -> dict[str, str]:
        headers = {
            "authorization": f"Bearer {self._upstream_api_key}",
            "content-type": "application/json",
        }
        organization = os.getenv("OPENAI_ORGANIZATION")
        project = os.getenv("OPENAI_PROJECT")
        if organization:
            headers["openai-organization"] = organization
        if project:
            headers["openai-project"] = project
        return headers

    async def _unsupported(self, request: Request) -> Response:
        del request
        return self._reject(
            "Unsupported or cost-bearing provider endpoint was rejected.", 404
        )

    async def _models(self, request: Request) -> Response:
        if not _authorized(request, self._local_token):
            return self._reject("Unauthorized loopback proxy request.", 401)
        return JSONResponse({"models": []})

    def _reject(self, message: str, status_code: int = 400) -> JSONResponse:
        self.ledger.fail(message)
        return JSONResponse({"error": {"message": message}}, status_code=status_code)


class CappedCodexRunner:
    def __init__(
        self,
        executable: str = "codex",
        *,
        supports_ignore_user_config: bool | None = None,
        upstream_base_url: str = "https://api.openai.com/v1",
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        self.executable = executable
        self._supports_ignore_user_config = supports_ignore_user_config
        self._upstream_base_url = upstream_base_url
        self._api_key_env = api_key_env

    @property
    def capabilities(self) -> AgentRunnerCapabilities:
        return AgentRunnerCapabilities(
            hard_reported_token_cap=True,
            reported_token_accounting=REPORTED_TOKEN_ACCOUNTING_ID,
            runner_id="capped-codex",
        )

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        if request.local_provider is not None:
            raise ValueError("capped-codex does not support local model providers.")
        if request.max_reported_tokens is None:
            raise ValueError(
                "capped-codex requires a per-execution reported-token cap."
            )
        upstream_api_key = os.getenv(self._api_key_env)
        if not upstream_api_key:
            raise RuntimeError(
                f"capped-codex requires the {self._api_key_env} environment variable."
            )
        local_token = secrets.token_urlsafe(32)
        proxy = CappedResponsesProxy(
            ceiling=request.max_reported_tokens,
            local_token=local_token,
            upstream_api_key=upstream_api_key,
            upstream_base_url=self._upstream_base_url,
        )
        bundled_model = await asyncio.to_thread(self._load_bundled_model, request.model)
        with tempfile.TemporaryDirectory(prefix="codemesh-capped-model-") as temp_dir:
            catalog_path = Path(temp_dir) / "models.json"
            catalog_path.write_text(
                json.dumps({"models": [bundled_model]}), encoding="utf-8"
            )
            async with proxy.serve() as base_url:
                runner = CodexRunner(
                    self.executable,
                    supports_ignore_user_config=self._supports_ignore_user_config,
                    config_overrides=_capped_provider_config(base_url, catalog_path),
                    environment_overrides={"CODEMESH_CAPPED_PROXY_TOKEN": local_token},
                )
                result = await runner.run(request)

        if proxy.ledger.request_count == 0:
            proxy.ledger.fail("Codex completed without a proxied Responses request.")
        elif (
            proxy.ledger.request_count != proxy.ledger.completed_request_count
            and not proxy.ledger.failures
        ):
            proxy.ledger.fail(
                "A Responses reservation remained unsettled after Codex exited."
            )
        for field in _USAGE_FIELDS:
            result.usage.setdefault(field, proxy.ledger.reported_usage[field])
        ledger = proxy.ledger.snapshot()
        if result.completed and ledger["complete"]:
            try:
                codex_reported_tokens = count_reported_tokens(result.usage)
            except ValueError as exc:
                proxy.ledger.fail(f"Codex final usage was invalid: {exc}")
            else:
                if codex_reported_tokens != ledger["reported_tokens"] or any(
                    result.usage.get(field) != ledger["usage"][field]
                    for field in _USAGE_FIELDS
                ):
                    proxy.ledger.fail(
                        "Codex final usage disagreed with the capped proxy ledger."
                    )
        elif result.completed:
            proxy.ledger.fail(
                "Codex declared completion without a complete capped proxy ledger."
            )

        ledger = proxy.ledger.snapshot()
        ledger["runner"] = "capped-codex"
        ledger["model_catalog_sha256"] = hashlib.sha256(
            json.dumps(bundled_model, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        if not ledger["complete"]:
            result.completed = False
            result.failures.extend(
                failure
                for failure in ledger["failures"]
                if failure not in result.failures
            )
        result.hard_cap_ledger = ledger
        return result

    def _load_bundled_model(self, model: str) -> dict[str, Any]:
        completed = subprocess.run(
            [self.executable, "debug", "models", "--bundled"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "capped-codex could not load the Codex bundled model catalog."
            )
        try:
            catalog = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "capped-codex received an invalid Codex bundled model catalog."
            ) from exc
        models = catalog.get("models") if isinstance(catalog, dict) else None
        if not isinstance(models, list):
            raise RuntimeError(
                "capped-codex received an invalid Codex bundled model catalog."
            )
        selected = next(
            (
                candidate
                for candidate in models
                if isinstance(candidate, dict) and candidate.get("slug") == model
            ),
            None,
        )
        if selected is None:
            raise RuntimeError(
                f"capped-codex cannot use model {model!r} because it is absent from "
                "the selected Codex executable's bundled catalog."
            )
        return selected


def _capped_provider_config(base_url: str, catalog_path: Path) -> tuple[str, ...]:
    prefix = "model_providers.codemesh_capped"
    return (
        'model_provider="codemesh_capped"',
        f"model_catalog_json={json.dumps(str(catalog_path))}",
        f'{prefix}.name="CodeMesh capped OpenAI"',
        f"{prefix}.base_url={json.dumps(base_url)}",
        f'{prefix}.env_key="CODEMESH_CAPPED_PROXY_TOKEN"',
        f'{prefix}.wire_api="responses"',
        f"{prefix}.requires_openai_auth=false",
        f"{prefix}.request_max_retries=0",
        f"{prefix}.stream_max_retries=0",
        f"{prefix}.supports_websockets=false",
    )


def _validate_response_request(body: Mapping[str, Any]) -> str | None:
    if set(body) - _ALLOWED_RESPONSE_FIELDS:
        return (
            "A Responses request parameter outside the capped runner's reviewed "
            "counting contract was rejected."
        )
    background = body.get("background")
    if background is not None and background is not False:
        return "Background Responses calls are unsupported by the capped runner."
    if body.get("context_management"):
        return "Automatic context compaction is unsupported by the capped runner."
    tools = body.get("tools") or []
    if not isinstance(tools, list):
        return "Responses tools must be an array."
    for tool in tools:
        if (
            not isinstance(tool, Mapping)
            or tool.get("type") not in _ALLOWED_LOCAL_TOOL_TYPES
        ):
            return "Unsupported cost-bearing Responses tool was rejected."
    return None


def _authorized(request: Request, expected_token: str) -> bool:
    authorization = request.headers.get("authorization", "")
    prefix = "Bearer "
    return authorization.startswith(prefix) and hmac.compare_digest(
        authorization[len(prefix) :], expected_token
    )


async def _wait_for_server(server: uvicorn.Server, task: asyncio.Task[None]) -> None:
    while not server.started:
        if task.done():
            await task
            raise RuntimeError("The capped Responses proxy stopped during startup.")
        await asyncio.sleep(0.01)


def _non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CappedProxyError(f"{field_name} must be a non-negative integer.")
    return value


def _optional_non_negative_integer(value: Any, field_name: str) -> int:
    if value is None:
        return 0
    return _non_negative_integer(value, field_name)
