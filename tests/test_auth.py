"""Tests for POST /api/v1/auth/register — S2 registration endpoint."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.core.security import verify_password
from app.db.models import TeamMember as TeamMemberRow
from app.db.models import User as UserRow
from tests.conftest import TEAM_ALPHA

API = "/api/v1/auth/register"

VALID_BODY = {
    "email": "newuser@example.com",
    "password": "Pass1234",
    "name": "New User",
    "team_id": str(TEAM_ALPHA),
}


# ---------------------------------------------------------------------------
# 1. Successful registration
# ---------------------------------------------------------------------------


class TestRegisterSuccess:
    """Tests for successful user registration."""

    async def test_register_returns_201(self, client):
        r = await client.post(API, json=VALID_BODY)
        assert r.status_code == 201

    async def test_register_returns_user_data(self, client):
        r = await client.post(API, json=VALID_BODY)
        body = r.json()
        assert "id" in body
        assert body["email"] == "newuser@example.com"
        assert body["name"] == "New User"
        # Password must never be returned
        assert "password" not in body
        assert "password_hash" not in body

    async def test_register_persists_user(self, client, db_session):
        r = await client.post(API, json=VALID_BODY)
        body = r.json()
        user_id = UUID(body["id"])

        from sqlalchemy import select

        result = await db_session.execute(select(UserRow).where(UserRow.id == user_id))
        user = result.scalar_one()
        assert user.email == "newuser@example.com"
        assert user.name == "New User"
        # Password must be hashed, not plaintext
        assert user.password_hash != "Pass1234"
        assert verify_password("Pass1234", user.password_hash)

    async def test_register_creates_team_membership(self, client, db_session):
        """Registration must create a TeamMember association (red line #10)."""
        r = await client.post(API, json=VALID_BODY)
        body = r.json()
        user_id = UUID(body["id"])

        from sqlalchemy import select

        result = await db_session.execute(
            select(TeamMemberRow).where(
                TeamMemberRow.user_id == user_id,
                TeamMemberRow.team_id == TEAM_ALPHA,
            )
        )
        membership = result.scalar_one()
        assert membership is not None
        assert membership.role == "member"

    async def test_register_email_normalized_to_lowercase(self, client, db_session):
        body = {**VALID_BODY, "email": "MixedCase@Example.COM"}
        r = await client.post(API, json=body)
        assert r.status_code == 201
        assert r.json()["email"] == "mixedcase@example.com"

        from sqlalchemy import select

        result = await db_session.execute(
            select(UserRow).where(UserRow.email == "mixedcase@example.com")
        )
        assert result.scalar_one() is not None


# ---------------------------------------------------------------------------
# 2. Duplicate email — must return generic message (anti-enumeration)
# ---------------------------------------------------------------------------


class TestRegisterDuplicate:
    """Duplicate email must not reveal that the email is registered."""

    async def test_duplicate_email_returns_409(self, client):
        await client.post(API, json=VALID_BODY)
        r = await client.post(API, json=VALID_BODY)
        assert r.status_code == 409

    async def test_duplicate_email_case_insensitive(self, client):
        await client.post(API, json=VALID_BODY)
        body2 = {**VALID_BODY, "email": "NEWUSER@EXAMPLE.COM"}
        r = await client.post(API, json=body2)
        assert r.status_code == 409

    async def test_duplicate_email_message_is_generic(self, client):
        """Error message must NOT reveal the email is already registered."""
        await client.post(API, json=VALID_BODY)
        r = await client.post(API, json=VALID_BODY)
        body = r.json()
        detail = body["detail"]
        # Must be a generic message, not "邮箱已注册" / "email already exists"
        assert "已注册" not in detail
        assert "已存在" not in detail
        assert "already" not in detail.lower()
        assert "注册失败" in detail


# ---------------------------------------------------------------------------
# 3. Invalid email format
# ---------------------------------------------------------------------------


class TestRegisterInvalidEmail:
    """Invalid email formats must return 422."""

    @pytest.mark.parametrize(
        "email",
        [
            "notanemail",
            "@example.com",
            "user@",
            "user@.com",
            "user@example",
            "user name@example.com",
            "",
        ],
    )
    async def test_invalid_email_returns_422(self, client, email):
        body = {**VALID_BODY, "email": email}
        r = await client.post(API, json=body)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 4. Weak password
# ---------------------------------------------------------------------------


class TestRegisterWeakPassword:
    """Passwords not meeting strength requirements must return 422."""

    @pytest.mark.parametrize(
        "password",
        [
            "short1A",  # 7 chars
            "alllowercase1",  # no uppercase
            "ALLUPPERCASE1",  # no lowercase
            "NoDigitsHere",  # no digit
            "12345678",  # only digits
            "",
        ],
    )
    async def test_weak_password_returns_422(self, client, password):
        body = {**VALID_BODY, "password": password}
        r = await client.post(API, json=body)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 5. Missing required fields
# ---------------------------------------------------------------------------


class TestRegisterMissingFields:
    """Missing required fields must return 422."""

    async def test_missing_email_returns_422(self, client):
        body = {k: v for k, v in VALID_BODY.items() if k != "email"}
        r = await client.post(API, json=body)
        assert r.status_code == 422

    async def test_missing_password_returns_422(self, client):
        body = {k: v for k, v in VALID_BODY.items() if k != "password"}
        r = await client.post(API, json=body)
        assert r.status_code == 422

    async def test_missing_name_returns_422(self, client):
        body = {k: v for k, v in VALID_BODY.items() if k != "name"}
        r = await client.post(API, json=body)
        assert r.status_code == 422

    async def test_missing_team_id_returns_422(self, client):
        body = {k: v for k, v in VALID_BODY.items() if k != "team_id"}
        r = await client.post(API, json=body)
        assert r.status_code == 422

    async def test_empty_body_returns_422(self, client):
        r = await client.post(API, json={})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 6. Invalid team_id
# ---------------------------------------------------------------------------


class TestRegisterInvalidTeam:
    """Registering with a non-existent team must return 404."""

    async def test_nonexistent_team_returns_404(self, client):
        body = {**VALID_BODY, "team_id": str(uuid4())}
        r = await client.post(API, json=body)
        assert r.status_code == 404
