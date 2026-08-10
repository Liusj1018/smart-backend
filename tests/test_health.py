"""Tests for health endpoint and error format consistency."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_health_endpoint(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_error_format_is_rfc7807(client: AsyncClient) -> None:
    """All errors must follow RFC 7807 + include trace_id."""
    from tests.conftest import ADMIN_HEADERS
    r = await client.get("/api/v1/members", params={"page": -1}, headers=ADMIN_HEADERS)
    assert r.status_code == 422
    body = r.json()
    for key in ("type", "title", "status", "detail", "instance", "trace_id"):
        assert key in body, f"Missing key: {key}"
    assert body["status"] == 422
    assert body["instance"] == "/api/v1/members"
    assert len(body["trace_id"]) > 0


async def test_trace_id_in_response_header(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert "X-Trace-Id" in r.headers
    assert len(r.headers["X-Trace-Id"]) > 0


async def test_client_provided_trace_id_is_echoed(client: AsyncClient) -> None:
    custom = "abc123def456"
    r = await client.get("/health", headers={"X-Trace-Id": custom})
    assert r.headers["X-Trace-Id"] == custom
