"""S8: Unified error response format — RFC 7807 with trace_id.

Every error response must:
- Follow RFC 7807 structure (type, title, status, detail, instance, trace_id)
- Include X-Trace-Id response header
- Use application/problem+json content type
- Not leak stack traces or internal details
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import ADMIN_HEADERS, SEED_PASSWORD, VIEWER_HEADERS

pytestmark = pytest.mark.asyncio

REQUIRED_FIELDS = {"type", "title", "status", "detail", "instance", "trace_id"}


def _assert_problem_json(resp, expected_status: int) -> dict:
    """Assert response is RFC 7807 compliant and return body."""
    assert resp.status_code == expected_status
    # Content-Type should be application/problem+json
    content_type = resp.headers.get("content-type", "")
    assert "application/problem+json" in content_type, (
        f"Expected application/problem+json, got {content_type}"
    )
    body = resp.json()
    # All required fields present
    assert REQUIRED_FIELDS.issubset(body.keys()), (
        f"Missing fields: {REQUIRED_FIELDS - body.keys()}"
    )
    # type matches status code
    assert body["type"] == f"https://httpstatuses.com/{expected_status}"
    # status field matches HTTP status
    assert body["status"] == expected_status
    # trace_id is non-empty string
    assert isinstance(body["trace_id"], str)
    assert len(body["trace_id"]) > 0
    # X-Trace-Id header matches body trace_id
    assert resp.headers.get("x-trace-id") == body["trace_id"]
    # instance is the request path
    assert body["instance"] == resp.request.url.path
    # No stack trace or internal details leaked
    detail_lower = body["detail"].lower()
    assert "traceback" not in detail_lower
    assert "sqlalchemy" not in detail_lower
    assert "psycopg" not in detail_lower
    assert "file \"" not in detail_lower
    return body


class Test401Unauthorized:
    """401 errors must follow RFC 7807."""

    async def test_no_token_returns_rfc7807(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/members")
        body = _assert_problem_json(resp, 401)
        assert body["title"] == "Unauthorized"

    async def test_invalid_token_returns_rfc7807(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/members",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        _assert_problem_json(resp, 401)

    async def test_expired_token_returns_rfc7807(self, client: AsyncClient) -> None:
        from app.core.jwt_tokens import create_access_token
        from tests.conftest import TEAM_ALPHA, USER_ALICE

        token = create_access_token(
            str(USER_ALICE), "admin", str(TEAM_ALPHA), expires_minutes=-1
        )
        resp = await client.get(
            "/api/v1/members",
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_problem_json(resp, 401)

    async def test_login_wrong_password_rfc7807(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "alice@alpha.com", "password": "WrongPass999"},
        )
        body = _assert_problem_json(resp, 401)
        assert body["detail"] == "用户名或密码错误"

    async def test_login_nonexistent_email_rfc7807(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "SomePass123"},
        )
        body = _assert_problem_json(resp, 401)
        assert body["detail"] == "用户名或密码错误"


class Test403Forbidden:
    """403 errors must follow RFC 7807."""

    async def test_viewer_cannot_delete_member(self, client: AsyncClient) -> None:
        # First get a member ID as admin
        list_resp = await client.get("/api/v1/members", headers=ADMIN_HEADERS)
        members = list_resp.json()["items"]
        member_id = members[0]["id"]

        # Viewer tries to delete
        resp = await client.delete(
            f"/api/v1/members/{member_id}", headers=VIEWER_HEADERS
        )
        body = _assert_problem_json(resp, 403)
        assert body["title"] == "Forbidden"


class Test404NotFound:
    """404 errors must follow RFC 7807."""

    async def test_nonexistent_route_rfc7807(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/nonexistent")
        body = _assert_problem_json(resp, 404)
        assert body["title"] == "Not Found"

    async def test_nonexistent_member_rfc7807(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/members/00000000-0000-0000-0000-000000000000",
            headers=ADMIN_HEADERS,
        )
        _assert_problem_json(resp, 404)

    async def test_nonexistent_commit_rfc7807(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/commits/00000000-0000-0000-0000-000000000000",
            headers=ADMIN_HEADERS,
        )
        _assert_problem_json(resp, 404)


class Test405MethodNotAllowed:
    """405 errors must follow RFC 7807."""

    async def test_method_not_allowed_rfc7807(self, client: AsyncClient) -> None:
        # PATCH is not allowed on /health
        resp = await client.patch("/health")
        body = _assert_problem_json(resp, 405)
        assert body["title"] == "Method Not Allowed"


class Test422Validation:
    """422 validation errors must follow RFC 7807."""

    async def test_invalid_pagination_rfc7807(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/api/v1/members?page=-1", headers=ADMIN_HEADERS
        )
        body = _assert_problem_json(resp, 422)
        assert body["title"] == "Validation Error"

    async def test_missing_login_fields_rfc7807(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/auth/login", json={})
        _assert_problem_json(resp, 422)

    async def test_invalid_email_format_rfc7807(self, client: AsyncClient) -> None:
        from tests.conftest import TEAM_ALPHA

        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": SEED_PASSWORD,
                "name": "Test User",
                "team_id": str(TEAM_ALPHA),
            },
        )
        _assert_problem_json(resp, 422)

    async def test_short_password_register_rfc7807(self, client: AsyncClient) -> None:
        from tests.conftest import TEAM_ALPHA

        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@alpha.com",
                "password": "short",
                "name": "New User",
                "team_id": str(TEAM_ALPHA),
            },
        )
        _assert_problem_json(resp, 422)


class TestTraceIdConsistency:
    """Trace ID must be consistent across header and body."""

    async def test_trace_id_in_header_and_body(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/members")
        body = resp.json()
        header_trace = resp.headers.get("x-trace-id")
        assert header_trace is not None
        assert body["trace_id"] == header_trace

    async def test_custom_trace_id_respected(self, client: AsyncClient) -> None:
        custom = "custom-trace-12345"
        resp = await client.get(
            "/api/v1/members", headers={"X-Trace-Id": custom}
        )
        assert resp.headers.get("x-trace-id") == custom
        assert resp.json()["trace_id"] == custom

    async def test_trace_id_on_success_too(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("x-trace-id") is not None

    async def test_each_error_has_unique_trace_id(self, client: AsyncClient) -> None:
        """Two different requests should have different trace_ids."""
        r1 = await client.get("/api/v1/members")
        r2 = await client.get("/api/v1/members")
        # If no custom header, each gets a unique trace_id
        t1 = r1.headers.get("x-trace-id")
        t2 = r2.headers.get("x-trace-id")
        assert t1 != t2


class TestNoInternalLeakage:
    """500 errors must not leak stack traces or internal details."""

    async def test_500_detail_is_generic(self, client: AsyncClient) -> None:
        """The catch-all handler returns a generic message."""
        # We can't easily trigger a real 500 in tests, but we can verify
        # the handler is registered by checking the app exception handlers
        from app.main import create_app

        app = create_app()
        # Verify the Exception handler is registered
        assert Exception in app.exception_handlers
        # Verify AppError handler is registered
        from app.exceptions import AppError

        assert AppError in app.exception_handlers
