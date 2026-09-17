from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest

import codemesh_agent_access.evaluation.capped_codex as capped_codex
from codemesh_agent_access.evaluation.capped_codex import (
    CappedCodexRunner,
    CappedProxyError,
    CappedResponsesProxy,
    HardCapLedger,
    _capped_provider_config,
    _validate_response_request,
)
from codemesh_agent_access.evaluation.codex import (
    REPORTED_TOKEN_ACCOUNTING_ID,
    AgentRunRequest,
    AgentRunResult,
)


class BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b'data: {"type":"response.created"}\n\n'
        raise httpx.ReadError("synthetic interrupted stream")


class StaticStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self._content = content

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield self._content


def test_hard_cap_ledger_enforces_exact_boundary_and_accounting() -> None:
    ledger = HardCapLedger(10)
    reservation, output_allowance = ledger.reserve(4, 20)

    assert output_allowance == 3
    assert ledger.snapshot()["remaining_tokens"] == 0

    ledger.settle(
        reservation,
        {
            "input_tokens": 4,
            "input_tokens_details": {"cached_tokens": 1},
            "output_tokens": 3,
            "output_tokens_details": {"reasoning_tokens": 3},
        },
    )

    assert ledger.snapshot() == {
        "accounting": REPORTED_TOKEN_ACCOUNTING_ID,
        "ceiling": 10,
        "committed_tokens": 10,
        "reported_tokens": 10,
        "retained_reservation_tokens": 0,
        "remaining_tokens": 0,
        "request_count": 1,
        "completed_request_count": 1,
        "usage": {
            "input_tokens": 4,
            "cached_input_tokens": 1,
            "output_tokens": 3,
            "reasoning_output_tokens": 3,
        },
        "request_max_retries": 0,
        "stream_max_retries": 0,
        "failures": [],
        "complete": True,
    }
    with pytest.raises(CappedProxyError, match="Insufficient remaining"):
        ledger.reserve(0, 1)


def test_hard_cap_ledger_supports_multiple_requests_and_rejects_disagreement() -> None:
    ledger = HardCapLedger(30)
    first, _ = ledger.reserve(4, 10)
    ledger.settle(
        first,
        {
            "input_tokens": 4,
            "output_tokens": 3,
            "output_tokens_details": {"reasoning_tokens": 1},
        },
    )
    second, allowance = ledger.reserve(5, 4)
    assert allowance == 4
    with pytest.raises(CappedProxyError, match="disagreed"):
        ledger.settle(
            second,
            {"input_tokens": 6, "output_tokens": 1},
        )


def test_hard_cap_ledger_clamps_to_provider_output_maximum() -> None:
    ledger = HardCapLedger(1_000_000)

    reservation, allowance = ledger.reserve(10, None)

    assert allowance == 128_000
    assert reservation.reserved_tokens == 256_010


def test_proxy_clamps_streamed_request_and_records_completed_usage() -> None:
    forwarded: list[dict[str, Any]] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/responses/input_tokens"):
            return httpx.Response(200, json={"input_tokens": 4})
        forwarded.append(json.loads(request.content))
        event = {
            "type": "response.completed",
            "response": {
                "usage": {
                    "input_tokens": 4,
                    "input_tokens_details": {"cached_tokens": 1},
                    "output_tokens": 5,
                    "output_tokens_details": {"reasoning_tokens": 2},
                }
            },
        }
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=StaticStream(f"data: {json.dumps(event)}\n\n".encode()),
        )

    proxy, upstream_client = _proxy(upstream, ceiling=14)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=proxy.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://proxy"
        ) as client:
            response = await client.post(
                "/v1/responses",
                headers={"authorization": "Bearer local-secret"},
                json={
                    "model": "test-model",
                    "input": "count all submitted input",
                    "stream": True,
                    "max_output_tokens": 99,
                    "tools": [{"type": "function", "name": "local_tool"}],
                },
            )
            assert response.status_code == 200
        await upstream_client.aclose()

    asyncio.run(exercise())

    assert forwarded[0]["max_output_tokens"] == 5
    snapshot = proxy.ledger.snapshot()
    assert snapshot["complete"] is True
    assert snapshot["reported_tokens"] == 11
    assert snapshot["remaining_tokens"] == 3


def test_proxy_retains_reservation_after_interrupted_stream() -> None:
    def upstream(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/responses/input_tokens"):
            return httpx.Response(200, json={"input_tokens": 4})
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=BrokenStream(),
        )

    proxy, upstream_client = _proxy(upstream, ceiling=10)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=proxy.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://proxy"
        ) as client:
            with pytest.raises(httpx.ReadError):
                await client.post(
                    "/v1/responses",
                    headers={"authorization": "Bearer local-secret"},
                    json={"model": "test-model", "input": "x", "stream": True},
                )
        await upstream_client.aclose()

    asyncio.run(exercise())

    snapshot = proxy.ledger.snapshot()
    assert snapshot["complete"] is False
    assert snapshot["committed_tokens"] == 10
    assert snapshot["retained_reservation_tokens"] == 10
    assert "interrupted" in " ".join(snapshot["failures"]).lower()


def test_proxy_rejects_missing_usage_backend_failure_and_duplicate_retry() -> None:
    response_calls = 0

    def upstream(request: httpx.Request) -> httpx.Response:
        nonlocal response_calls
        if request.url.path.endswith("/responses/input_tokens"):
            return httpx.Response(200, json={"input_tokens": 2})
        response_calls += 1
        event = {"type": "response.completed", "response": {}}
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=StaticStream(f"data: {json.dumps(event)}\n\n".encode()),
        )

    proxy, upstream_client = _proxy(upstream, ceiling=8)
    body = {"model": "test-model", "input": "x", "stream": True}

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=proxy.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://proxy"
        ) as client:
            first = await client.post(
                "/v1/responses",
                headers={"authorization": "Bearer local-secret"},
                json=body,
            )
            assert first.status_code == 200
            second = await client.post(
                "/v1/responses",
                headers={"authorization": "Bearer local-secret"},
                json=body,
            )
            assert second.status_code == 400
        await upstream_client.aclose()

    asyncio.run(exercise())

    assert response_calls == 1
    snapshot = proxy.ledger.snapshot()
    assert snapshot["committed_tokens"] == 8
    assert snapshot["completed_request_count"] == 0
    assert any("usage" in failure for failure in snapshot["failures"])
    assert any("retry" in failure for failure in snapshot["failures"])


def test_proxy_fails_closed_without_exposing_secrets() -> None:
    def upstream(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("backend failed with upstream-secret")

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    proxy = CappedResponsesProxy(
        ceiling=10,
        local_token="local-secret",
        upstream_api_key="upstream-secret",
        upstream_base_url="https://upstream.test/v1",
        upstream_client=upstream_client,
    )

    async def exercise() -> str:
        transport = httpx.ASGITransport(app=proxy.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://proxy"
        ) as client:
            response = await client.post(
                "/v1/responses",
                headers={"authorization": "Bearer local-secret"},
                json={"model": "test-model", "input": "x"},
            )
        await upstream_client.aclose()
        return response.text

    response_text = asyncio.run(exercise())
    retained = json.dumps(proxy.ledger.snapshot()) + response_text
    assert "local-secret" not in retained
    assert "upstream-secret" not in retained
    assert "Input-token counting failed closed" in retained


def test_proxy_handles_cost_free_model_discovery_without_poisoning_ledger() -> None:
    proxy, upstream_client = _proxy(lambda _request: httpx.Response(500), ceiling=10)

    async def exercise() -> dict[str, Any]:
        transport = httpx.ASGITransport(app=proxy.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://proxy"
        ) as client:
            response = await client.get(
                "/v1/models?client_version=test",
                headers={"authorization": "Bearer local-secret"},
            )
        await upstream_client.aclose()
        assert response.status_code == 200
        return response.json()

    assert asyncio.run(exercise()) == {"models": []}
    assert proxy.ledger.failures == []


def test_capped_runner_declares_cap_and_zero_retry_provider_configuration() -> None:
    runner = CappedCodexRunner()

    assert runner.capabilities.hard_reported_token_cap is True
    assert runner.capabilities.reported_token_accounting == REPORTED_TOKEN_ACCOUNTING_ID
    config = _capped_provider_config(
        "http://127.0.0.1:1234/v1", Path("/tmp/capped-models.json")
    )
    assert "model_providers.codemesh_capped.request_max_retries=0" in config
    assert "model_providers.codemesh_capped.stream_max_retries=0" in config
    assert "model_providers.codemesh_capped.supports_websockets=false" in config
    assert any(value.startswith("model_catalog_json=") for value in config)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"background": True}, "Background"),
        ({"context_management": [{"type": "compaction"}]}, "compaction"),
        ({"prompt": {"id": "prompt_123"}}, "counting contract"),
        ({"future_input": "unreviewed"}, "counting contract"),
        ({"tools": [{"type": "web_search"}]}, "cost-bearing"),
        ({"tools": "not-an-array"}, "array"),
    ],
)
def test_capped_proxy_rejects_unsupported_cost_activity(
    body: dict[str, Any], message: str
) -> None:
    assert message in str(_validate_response_request(body))


def test_capped_runner_rejects_codex_proxy_usage_disagreement(
    monkeypatch: Any, tmp_path: Path
) -> None:
    ledger = HardCapLedger(100)
    reservation, _ = ledger.reserve(10, 20)
    ledger.settle(
        reservation,
        {
            "input_tokens": 10,
            "output_tokens": 5,
            "output_tokens_details": {"reasoning_tokens": 2},
        },
    )

    class FakeProxy:
        def __init__(self, **_kwargs: Any) -> None:
            self.ledger = ledger

        @asynccontextmanager
        async def serve(self) -> AsyncIterator[str]:
            yield "http://127.0.0.1:1234/v1"

    class FakeCodexRunner:
        def __init__(self, *_args: Any, **kwargs: Any) -> None:
            assert kwargs["environment_overrides"].keys() == {
                "CODEMESH_CAPPED_PROXY_TOKEN"
            }
            assert (
                "model_providers.codemesh_capped.request_max_retries=0"
                in kwargs["config_overrides"]
            )

        async def run(self, _request: AgentRunRequest) -> AgentRunResult:
            return AgentRunResult(
                completed=True,
                exit_code=0,
                duration_ms=1,
                usage={
                    "input_tokens": 10,
                    "cached_input_tokens": 0,
                    "output_tokens": 4,
                    "reasoning_output_tokens": 2,
                },
            )

    monkeypatch.setenv("OPENAI_API_KEY", "test-upstream-secret")
    monkeypatch.setattr(capped_codex, "CappedResponsesProxy", FakeProxy)
    monkeypatch.setattr(capped_codex, "CodexRunner", FakeCodexRunner)
    monkeypatch.setattr(
        CappedCodexRunner,
        "_load_bundled_model",
        lambda _self, model: {"slug": model},
    )
    request = AgentRunRequest(
        prompt="test",
        cwd=tmp_path,
        condition="control",
        model="test-model",
        reasoning_effort="medium",
        sandbox="read-only",
        timeout_seconds=30,
        mcp_cwd=tmp_path,
        max_reported_tokens=100,
    )

    result = asyncio.run(CappedCodexRunner().run(request))

    assert result.completed is False
    assert result.hard_cap_ledger is not None
    assert result.hard_cap_ledger["complete"] is False
    assert any("disagreed" in failure for failure in result.failures)
    assert "test-upstream-secret" not in json.dumps(result.hard_cap_ledger)


def _proxy(
    handler: Any, *, ceiling: int
) -> tuple[CappedResponsesProxy, httpx.AsyncClient]:
    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return (
        CappedResponsesProxy(
            ceiling=ceiling,
            local_token="local-secret",
            upstream_api_key="upstream-secret",
            upstream_base_url="https://upstream.test/v1",
            upstream_client=upstream_client,
        ),
        upstream_client,
    )
