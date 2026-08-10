"""Tests for POST /api/v1/auth/login — S3 login endpoint."""

from __future__ import annotations

import jwt
import pytest

from app.config import settings
from app.core.jwt_tokens import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from tests.conftest import SEED_PASSWORD

API = "/api/v1/auth/login"

VALID_BODY = {
    "email": "alice@alpha.com",
    "password": SEED_PASSWORD,
}


# ---------------------------------------------------------------------------
# 1. Successful login
# ---------------------------------------------------------------------------


class TestLoginSuccess:
    """Tests for successful user login."""

    async def test_login_returns_200(self, client):
        r = await client.post(API, json=VALID_BODY)
        assert r.status_code == 200

    async def test_login_returns_tokens(self, client):
        r = await client.post(API, json=VALID_BODY)
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == settings.access_token_expire_minutes * 60

    async def test_access_token_is_valid_jwt(self, client):
        r = await client.post(API, json=VALID_BODY)
        token = r.json()["access_token"]
        payload = decode_token(token)
        assert payload["type"] == TOKEN_TYPE_ACCESS
        assert "sub" in payload
        assert "role" in payload
        assert "team_id" in payload
        assert "exp" in payload
        assert "iat" in payload

    async def test_refresh_token_is_valid_jwt(self, client):
        r = await client.post(API, json=VALID_BODY)
        token = r.json()["refresh_token"]
        payload = decode_token(token)
        assert payload["type"] == TOKEN_TYPE_REFRESH
        assert "sub" in payload
        assert "exp" in payload
        assert "iat" in payload
        # Refresh token must NOT contain role or team_id
        assert "role" not in payload
        assert "team_id" not in payload

    async def test_access_token_expires_in_15_minutes(self, client):
        r = await client.post(API, json=VALID_BODY)
        token = r.json()["access_token"]
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        # exp - iat should be 15 minutes = 900 seconds
        assert payload["exp"] - payload["iat"] == 15 * 60

    async def test_refresh_token_expires_in_7_days(self, client):
        r = await client.post(API, json=VALID_BODY)
        token = r.json()["refresh_token"]
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        # exp - iat should be 7 days = 604800 seconds
        assert payload["exp"] - payload["iat"] == 7 * 24 * 60 * 60

    async def test_login_email_case_insensitive(self, client):
        body = {**VALID_BODY, "email": "ALICE@ALPHA.COM"}
        r = await client.post(API, json=body)
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_admin_user_gets_admin_role_in_token(self, client):
        body = {"email": "alice@alpha.com", "password": SEED_PASSWORD}
        r = await client.post(API, json=body)
        token = r.json()["access_token"]
        payload = decode_token(token)
        assert payload["role"] == "admin"

    async def test_developer_user_gets_developer_role_in_token(self, client):
        body = {"email": "bob@alpha.com", "password": SEED_PASSWORD}
        r = await client.post(API, json=body)
        token = r.json()["access_token"]
        payload = decode_token(token)
        assert payload["role"] == "developer"

    async def test_response_does_not_contain_password(self, client):
        r = await client.post(API, json=VALID_BODY)
        body = r.json()
        assert "password" not in body
        assert "password_hash" not in body


# ---------------------------------------------------------------------------
# 2. Failed login — wrong password
# ---------------------------------------------------------------------------


class TestLoginWrongPassword:
    """Wrong password must return 401 with generic message."""

    async def test_wrong_password_returns_401(self, client):
        body = {**VALID_BODY, "password": "WrongPass999"}
        r = await client.post(API, json=body)
        assert r.status_code == 401

    async def test_wrong_password_message_is_generic(self, client):
        body = {**VALID_BODY, "password": "WrongPass999"}
        r = await client.post(API, json=body)
        detail = r.json()["detail"]
        # Must use the exact generic message that doesn't reveal which field was wrong
        assert detail == "用户名或密码错误"


# ---------------------------------------------------------------------------
# 3. Failed login — non-existent email
# ---------------------------------------------------------------------------


class TestLoginNonExistentEmail:
    """Non-existent email must return 401 with same generic message."""

    async def test_nonexistent_email_returns_401(self, client):
        body = {"email": "nobody@example.com", "password": "SomePass123"}
        r = await client.post(API, json=body)
        assert r.status_code == 401

    async def test_nonexistent_email_same_message_as_wrong_password(self, client):
        """Anti-enumeration: same error for bad email and bad password."""
        r1 = await client.post(API, json={"email": "nobody@example.com", "password": "SomePass123"})
        r2 = await client.post(API, json={**VALID_BODY, "password": "WrongPass999"})
        assert r1.json()["detail"] == r2.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Missing required fields
# ---------------------------------------------------------------------------


class TestLoginMissingFields:
    """Missing required fields must return 422."""

    async def test_missing_email_returns_422(self, client):
        body = {"password": SEED_PASSWORD}
        r = await client.post(API, json=body)
        assert r.status_code == 422

    async def test_missing_password_returns_422(self, client):
        body = {"email": "alice@alpha.com"}
        r = await client.post(API, json=body)
        assert r.status_code == 422

    async def test_empty_body_returns_422(self, client):
        r = await client.post(API, json={})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 5. JWT token unit tests
# ---------------------------------------------------------------------------


class TestJwtTokens:
    """Unit tests for JWT token creation and verification."""

    def test_create_and_decode_access_token(self):
        token = create_access_token("user-123", "admin", "team-456")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"
        assert payload["team_id"] == "team-456"
        assert payload["type"] == TOKEN_TYPE_ACCESS

    def test_create_and_decode_refresh_token(self):
        token, _jti, _fam = create_refresh_token("user-123")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == TOKEN_TYPE_REFRESH
        assert "role" not in payload
        assert "jti" in payload
        assert "fam" in payload

    def test_invalid_token_raises(self):
        with pytest.raises(jwt.InvalidTokenError):
            decode_token("not.a.valid.token")

    def test_expired_token_raises(self):
        """Manually craft an expired token and verify decode rejects it."""
        from datetime import UTC, datetime, timedelta

        payload = {
            "sub": "user-123",
            "type": TOKEN_TYPE_ACCESS,
            "exp": datetime.now(UTC) - timedelta(seconds=1),
            "iat": datetime.now(UTC) - timedelta(seconds=2),
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(token)
