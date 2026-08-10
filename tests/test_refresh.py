"""Tests for POST /api/v1/auth/refresh — S4 token refresh with rotation."""

from __future__ import annotations

import time

import jwt
import pytest

from app.config import settings
from app.core.jwt_tokens import create_refresh_token, decode_token
from app.middleware.token_blacklist import TokenBlacklist, token_blacklist

API = "/api/v1/auth/refresh"
LOGIN_API = "/api/v1/auth/login"

SEED_EMAIL = "alice@alpha.com"
SEED_PASSWORD = "TestPass123"


@pytest.fixture(autouse=True)
def _clear_blacklist():
    """Reset the in-memory blacklist before each test."""
    token_blacklist._tokens.clear()
    token_blacklist._families.clear()
    yield
    token_blacklist._tokens.clear()
    token_blacklist._families.clear()


async def _login(client) -> dict:
    """Helper: log in and return the token response."""
    r = await client.post(
        LOGIN_API,
        json={"email": SEED_EMAIL, "password": SEED_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. Successful refresh
# ---------------------------------------------------------------------------


class TestRefreshSuccess:
    """Valid refresh token should return new token pair."""

    async def test_refresh_returns_200(self, client):
        tokens = await _login(client)
        r = await client.post(API, json={"refresh_token": tokens["refresh_token"]})
        assert r.status_code == 200

    async def test_refresh_returns_new_tokens(self, client):
        tokens = await _login(client)
        r = await client.post(API, json={"refresh_token": tokens["refresh_token"]})
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == settings.access_token_expire_minutes * 60

    async def test_new_access_token_is_valid(self, client):
        tokens = await _login(client)
        r = await client.post(API, json={"refresh_token": tokens["refresh_token"]})
        body = r.json()
        # New access token must decode without error
        payload = decode_token(body["access_token"])
        assert payload["type"] == "access"
        assert "sub" in payload

    async def test_new_refresh_token_is_different(self, client):
        """Rotation: the new refresh token must differ from the old one."""
        tokens = await _login(client)
        old_rt = tokens["refresh_token"]
        r = await client.post(API, json={"refresh_token": old_rt})
        new_rt = r.json()["refresh_token"]
        assert new_rt != old_rt

    async def test_new_refresh_token_same_family(self, client):
        """Rotated tokens must share the same family ID."""
        tokens = await _login(client)
        old_payload = decode_token(tokens["refresh_token"])
        r = await client.post(API, json={"refresh_token": tokens["refresh_token"]})
        new_payload = decode_token(r.json()["refresh_token"])
        assert new_payload["fam"] == old_payload["fam"]
        # jti must be different (unique per token)
        assert new_payload["jti"] != old_payload["jti"]

    async def test_rotation_chain_works(self, client):
        """Multiple sequential refreshes should all succeed."""
        tokens = await _login(client)
        rt = tokens["refresh_token"]
        for _ in range(3):
            r = await client.post(API, json={"refresh_token": rt})
            assert r.status_code == 200
            rt = r.json()["refresh_token"]


# ---------------------------------------------------------------------------
# 2. Old refresh token cannot be reused (one-time use)
# ---------------------------------------------------------------------------


class TestRefreshTokenReuse:
    """A used refresh token must be rejected on second use."""

    async def test_old_token_rejected_after_refresh(self, client):
        tokens = await _login(client)
        old_rt = tokens["refresh_token"]
        # First use — succeeds
        r1 = await client.post(API, json={"refresh_token": old_rt})
        assert r1.status_code == 200
        # Second use of same token — rejected
        r2 = await client.post(API, json={"refresh_token": old_rt})
        assert r2.status_code == 401

    async def test_replay_message_indicates_anomaly(self, client):
        tokens = await _login(client)
        old_rt = tokens["refresh_token"]
        await client.post(API, json={"refresh_token": old_rt})
        r = await client.post(API, json={"refresh_token": old_rt})
        body = r.json()
        assert "异常" in body["detail"] or "重新登录" in body["detail"]


# ---------------------------------------------------------------------------
# 3. Replay attack invalidates entire family
# ---------------------------------------------------------------------------


class TestRefreshReplayAttack:
    """If an old token is replayed, the whole family is compromised."""

    async def test_replay_invalidates_newer_token(self, client):
        """After replay, even the legitimately-issued new token is rejected."""
        tokens = await _login(client)
        rt_v1 = tokens["refresh_token"]

        # Legitimate refresh: v1 -> v2
        r = await client.post(API, json={"refresh_token": rt_v1})
        rt_v2 = r.json()["refresh_token"]

        # Attacker replays v1
        r_replay = await client.post(API, json={"refresh_token": rt_v1})
        assert r_replay.status_code == 401

        # v2 must now also be rejected (family compromised)
        r_v2 = await client.post(API, json={"refresh_token": rt_v2})
        assert r_v2.status_code == 401


# ---------------------------------------------------------------------------
# 4. Expired refresh token
# ---------------------------------------------------------------------------


class TestRefreshExpired:
    """Expired refresh token must return 401 with '请重新登录'."""

    async def test_expired_token_returns_401(self, client):
        # Create an already-expired token
        payload = {
            "sub": "00000000-0000-0000-0000-000000000001",
            "type": "refresh",
            "jti": "test-jti-expired",
            "fam": "test-fam-expired",
            "exp": int(time.time()) - 3600,  # 1 hour ago
            "iat": int(time.time()) - 7200,
        }
        expired_token = jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
        r = await client.post(API, json={"refresh_token": expired_token})
        assert r.status_code == 401

    async def test_expired_token_message(self, client):
        payload = {
            "sub": "00000000-0000-0000-0000-000000000001",
            "type": "refresh",
            "jti": "test-jti-expired2",
            "fam": "test-fam-expired2",
            "exp": int(time.time()) - 3600,
            "iat": int(time.time()) - 7200,
        }
        expired_token = jwt.encode(
            payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
        r = await client.post(API, json={"refresh_token": expired_token})
        assert "重新登录" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 5. Invalid tokens
# ---------------------------------------------------------------------------


class TestRefreshInvalid:
    """Malformed or wrong-type tokens must be rejected."""

    async def test_garbage_token_returns_401(self, client):
        r = await client.post(API, json={"refresh_token": "not.a.valid.jwt"})
        assert r.status_code == 401

    async def test_access_token_cannot_refresh(self, client):
        """An access token must not be accepted at the refresh endpoint."""
        tokens = await _login(client)
        # Use the access token instead of refresh token
        r = await client.post(API, json={"refresh_token": tokens["access_token"]})
        assert r.status_code == 401

    async def test_token_signed_with_wrong_secret(self, client):
        payload = {
            "sub": "00000000-0000-0000-0000-000000000001",
            "type": "refresh",
            "jti": "test-jti-badsecret",
            "fam": "test-fam-badsecret",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        bad_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        r = await client.post(API, json={"refresh_token": bad_token})
        assert r.status_code == 401

    async def test_nonexistent_user_returns_401(self, client):
        """Token for a user that no longer exists must be rejected."""
        token, _jti, _fam = create_refresh_token(
            "00000000-0000-0000-0000-000000000099"
        )
        r = await client.post(API, json={"refresh_token": token})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# 6. Missing / empty fields
# ---------------------------------------------------------------------------


class TestRefreshValidation:
    """Request body validation."""

    async def test_missing_refresh_token_returns_422(self, client):
        r = await client.post(API, json={})
        assert r.status_code == 422

    async def test_empty_refresh_token_returns_422(self, client):
        r = await client.post(API, json={"refresh_token": ""})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 7. Unit tests for TokenBlacklist
# ---------------------------------------------------------------------------


class TestTokenBlacklistUnit:
    """Direct unit tests for the blacklist data structure."""

    def test_new_token_not_blacklisted(self):
        bl = TokenBlacklist()
        assert bl.is_blacklisted("jti-1") is False

    def test_revoked_token_is_blacklisted(self):
        bl = TokenBlacklist()
        bl.revoke("jti-1", "fam-1")
        assert bl.is_blacklisted("jti-1") is True

    def test_family_not_compromised_initially(self):
        bl = TokenBlacklist()
        bl.revoke("jti-1", "fam-1")
        assert bl.is_family_compromised("fam-1") is False

    def test_replay_marks_family_compromised(self):
        bl = TokenBlacklist()
        bl.revoke("jti-1", "fam-1")
        # Replay same jti
        bl.revoke("jti-1", "fam-1")
        assert bl.is_family_compromised("fam-1") is True

    def test_different_families_independent(self):
        bl = TokenBlacklist()
        bl.revoke("jti-1", "fam-1")
        bl.revoke("jti-1", "fam-1")  # replay in fam-1
        assert bl.is_family_compromised("fam-1") is True
        assert bl.is_family_compromised("fam-2") is False
