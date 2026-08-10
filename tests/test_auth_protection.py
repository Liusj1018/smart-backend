"""Tests verifying that protected endpoints return 401 without a valid JWT."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import TEAM_ALPHA, USER_ALICE

pytestmark = pytest.mark.asyncio

PROTECTED_GET_PATHS = [
    "/api/v1/members",
    "/api/v1/commits",
]

PROTECTED_POST_PATHS = [
    "/api/v1/members",
]


class TestProtectedEndpoints401:
    """Every protected endpoint must return 401 without a Bearer token."""

    @pytest.mark.parametrize("path", PROTECTED_GET_PATHS)
    async def test_get_without_token_returns_401(
        self, client: AsyncClient, path: str
    ) -> None:
        resp = await client.get(path)
        assert resp.status_code == 401
        body = resp.json()
        assert body["type"] == "https://httpstatuses.com/401"

    @pytest.mark.parametrize("path", PROTECTED_POST_PATHS)
    async def test_post_without_token_returns_401(
        self, client: AsyncClient, path: str
    ) -> None:
        resp = await client.post(path, json={})
        assert resp.status_code == 401

    async def test_get_with_invalid_token_returns_401(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get(
            "/api/v1/members",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    async def test_get_with_expired_token_returns_401(
        self, client: AsyncClient
    ) -> None:
        from app.core.jwt_tokens import create_access_token

        expired = create_access_token(
            str(USER_ALICE),
            "admin",
            str(TEAM_ALPHA),
            expires_minutes=-1,
        )
        resp = await client.get(
            "/api/v1/members",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert resp.status_code == 401

    async def test_get_with_refresh_token_returns_401(
        self, client: AsyncClient
    ) -> None:
        from app.core.jwt_tokens import create_refresh_token

        refresh, _jti, _fam = create_refresh_token(str(USER_ALICE))
        resp = await client.get(
            "/api/v1/members",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert resp.status_code == 401

    async def test_health_is_public(self, client: AsyncClient) -> None:
        """/health must remain accessible without authentication."""
        resp = await client.get("/health")
        assert resp.status_code == 200
