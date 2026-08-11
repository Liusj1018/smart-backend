"""Tests for member CRUD endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import ADMIN_HEADERS, BETA_HEADERS, DEV_HEADERS, TEAM_ALPHA, TEAM_BETA, VIEWER_HEADERS

pytestmark = pytest.mark.anyio

API = "/api/v1/members"


# ---------- list ----------

async def test_list_members_returns_seed_data(client: AsyncClient) -> None:
    r = await client.get(API, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    assert body["page"] == 1
    assert len(body["items"]) == 4
    assert "X-Trace-Id" in r.headers


async def test_list_members_pagination(client: AsyncClient) -> None:
    r = await client.get(API, params={"page": 1, "page_size": 2}, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] == 4
    assert body["total_pages"] == 2


async def test_list_members_filter_by_role(client: AsyncClient) -> None:
    r = await client.get(API, params={"role": "admin"}, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["role"] == "admin"


async def test_list_members_filter_by_name(client: AsyncClient) -> None:
    r = await client.get(API, params={"name": "Alice"}, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert "Alice" in body["items"][0]["name"]


async def test_list_members_page_zero_rejected(client: AsyncClient) -> None:
    r = await client.get(API, params={"page": 0}, headers=ADMIN_HEADERS)
    assert r.status_code == 422
    assert r.json()["trace_id"]


async def test_list_members_negative_page_rejected(client: AsyncClient) -> None:
    r = await client.get(API, params={"page": -1}, headers=ADMIN_HEADERS)
    assert r.status_code == 422
    body = r.json()
    assert body["title"] == "Validation Error"
    assert body["trace_id"]


async def test_list_members_missing_token(client: AsyncClient) -> None:
    """No Authorization header → 401."""
    r = await client.get(API)
    assert r.status_code == 401


async def test_write_ignores_x_user_role_header(client: AsyncClient) -> None:
    """X-User-Role header must not grant admin — role comes from JWT/DB."""
    # Bob is a developer; forging X-User-Role: admin must not elevate privileges.
    headers = {**DEV_HEADERS, "X-User-Role": "admin"}
    payload = {
        "name": "X",
        "email": "x@example.com",
        "password": "SecurePass123",
        "role": "developer",
    }
    r = await client.post(API, json=payload, headers=headers)
    assert r.status_code == 403


async def test_cross_team_access_returns_404(client: AsyncClient) -> None:
    """A member from team-beta must not be visible to team-alpha (404, not 403)."""
    beta_members = (await client.get(API, headers=BETA_HEADERS)).json()["items"]
    bid = beta_members[0]["id"]
    r = await client.get(f"{API}/{bid}", headers=ADMIN_HEADERS)
    assert r.status_code == 404


async def test_cross_team_update_returns_404(client: AsyncClient) -> None:
    """Updating a member from another team returns 404."""
    beta_members = (await client.get(API, headers=BETA_HEADERS)).json()["items"]
    bid = beta_members[0]["id"]
    r = await client.put(
        f"{API}/{bid}",
        json={"name": "Hacked"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 404


async def test_cross_team_delete_returns_404(client: AsyncClient) -> None:
    """Deleting a member from another team returns 404."""
    beta_members = (await client.get(API, headers=BETA_HEADERS)).json()["items"]
    bid = beta_members[0]["id"]
    r = await client.delete(f"{API}/{bid}", headers=ADMIN_HEADERS)
    assert r.status_code == 404


async def test_x_team_id_header_ignored(client: AsyncClient) -> None:
    """Forging X-Team-Id must not change the tenant scope."""
    # Alice is in team-alpha; forging X-Team-Id to team-beta must NOT
    # return beta members — the team_id comes from the JWT.
    headers = {**ADMIN_HEADERS, "X-Team-Id": str(TEAM_BETA)}
    r = await client.get(API, headers=headers)
    assert r.status_code == 200
    alpha_ids = {m["id"] for m in r.json()["items"]}
    beta_members = (await client.get(API, headers=BETA_HEADERS)).json()["items"]
    beta_ids = {m["id"] for m in beta_members}
    assert alpha_ids.isdisjoint(beta_ids)


# ---------- multi-tenant isolation ----------

async def test_tenant_isolation(client: AsyncClient) -> None:
    r_alpha = await client.get(API, headers=ADMIN_HEADERS)
    r_beta = await client.get(API, headers=BETA_HEADERS)
    alpha_ids = {m["id"] for m in r_alpha.json()["items"]}
    beta_ids = {m["id"] for m in r_beta.json()["items"]}
    assert alpha_ids.isdisjoint(beta_ids)


# ---------- get detail ----------

async def test_get_member_detail(client: AsyncClient) -> None:
    members = (await client.get(API, headers=ADMIN_HEADERS)).json()["items"]
    mid = members[0]["id"]
    r = await client.get(f"{API}/{mid}", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == mid
    assert body["team_id"] == str(TEAM_ALPHA)
    assert "email" in body


async def test_get_member_not_found(client: AsyncClient) -> None:
    r = await client.get(f"{API}/00000000-0000-0000-0000-000000000000", headers=ADMIN_HEADERS)
    assert r.status_code == 404
    body = r.json()
    assert body["title"] == "Not Found"
    assert body["trace_id"]


async def test_get_member_other_team_not_found(client: AsyncClient) -> None:
    """A member from team-beta must not be visible to team-alpha."""
    beta_members = (await client.get(API, headers=BETA_HEADERS)).json()["items"]
    bid = beta_members[0]["id"]
    r = await client.get(f"{API}/{bid}", headers=ADMIN_HEADERS)
    assert r.status_code == 404


# ---------- create ----------

async def test_create_member_admin(client: AsyncClient) -> None:
    payload = {
        "name": "New Dev",
        "email": "new@example.com",
        "password": "SecurePass123",
        "role": "developer",
    }
    r = await client.post(API, json=payload, headers=ADMIN_HEADERS)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "New Dev"
    assert body["role"] == "developer"


async def test_create_member_forbidden_for_viewer(client: AsyncClient) -> None:
    payload = {
        "name": "X",
        "email": "x@example.com",
        "password": "SecurePass123",
        "role": "developer",
    }
    r = await client.post(API, json=payload, headers=VIEWER_HEADERS)
    assert r.status_code == 403
    assert r.json()["title"] == "Forbidden"


async def test_create_member_forbidden_for_developer(client: AsyncClient) -> None:
    payload = {
        "name": "X",
        "email": "x@example.com",
        "password": "SecurePass123",
        "role": "developer",
    }
    r = await client.post(API, json=payload, headers=DEV_HEADERS)
    assert r.status_code == 403


async def test_create_member_invalid_role(client: AsyncClient) -> None:
    payload = {
        "name": "X",
        "email": "x@example.com",
        "password": "SecurePass123",
        "role": "superadmin",
    }
    r = await client.post(API, json=payload, headers=ADMIN_HEADERS)
    assert r.status_code == 422


async def test_create_member_invalid_email(client: AsyncClient) -> None:
    payload = {
        "name": "X",
        "email": "not-an-email",
        "password": "SecurePass123",
        "role": "developer",
    }
    r = await client.post(API, json=payload, headers=ADMIN_HEADERS)
    assert r.status_code == 422


# ---------- update ----------

async def test_update_member(client: AsyncClient) -> None:
    members = (await client.get(API, headers=ADMIN_HEADERS)).json()["items"]
    mid = members[0]["id"]
    r = await client.put(
        f"{API}/{mid}",
        json={"name": "Updated Name"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Name"


async def test_update_member_forbidden(client: AsyncClient) -> None:
    members = (await client.get(API, headers=ADMIN_HEADERS)).json()["items"]
    mid = members[0]["id"]
    r = await client.put(f"{API}/{mid}", json={"name": "X"}, headers=VIEWER_HEADERS)
    assert r.status_code == 403


async def test_update_member_partial_fields(client: AsyncClient) -> None:
    """PUT with individual optional fields: email, role, github_username."""
    members = (await client.get(f"{API}", headers=ADMIN_HEADERS)).json()["items"]
    # Use Bob (developer, index 1) — not Alice the admin — to avoid self-demotion.
    mid = members[1]["id"]

    # update email only
    r = await client.put(
        f"{API}/{mid}",
        json={"email": "newemail@example.com"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["email"] == "newemail@example.com"

    # update role only
    r = await client.put(
        f"{API}/{mid}",
        json={"role": "viewer"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["role"] == "viewer"

    # update github_username only
    r = await client.put(
        f"{API}/{mid}",
        json={"github_username": "newgh"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["github_username"] == "newgh"


async def test_update_member_not_found(client: AsyncClient) -> None:
    r = await client.put(
        f"{API}/00000000-0000-0000-0000-000000000000",
        json={"name": "X"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 404


# ---------- delete ----------

async def test_delete_member(client: AsyncClient) -> None:
    members = (await client.get(API, headers=ADMIN_HEADERS)).json()["items"]
    mid = members[-1]["id"]
    r = await client.delete(f"{API}/{mid}", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["message"] == "删除成功"
    r2 = await client.get(f"{API}/{mid}", headers=ADMIN_HEADERS)
    assert r2.status_code == 404


async def test_delete_member_forbidden(client: AsyncClient) -> None:
    members = (await client.get(API, headers=ADMIN_HEADERS)).json()["items"]
    mid = members[0]["id"]
    r = await client.delete(f"{API}/{mid}", headers=DEV_HEADERS)
    assert r.status_code == 403


async def test_delete_member_not_found(client: AsyncClient) -> None:
    r = await client.delete(
        f"{API}/00000000-0000-0000-0000-000000000000", headers=ADMIN_HEADERS
    )
    assert r.status_code == 404


async def test_delete_self_forbidden(client: AsyncClient) -> None:
    """An admin must not be able to delete their own account."""
    members = (await client.get(API, headers=ADMIN_HEADERS)).json()["items"]
    # Alice is the admin (first member in seed data, USER_ALICE)
    alice = next(m for m in members if m["name"] == "Alice Admin")
    r = await client.delete(f"{API}/{alice['id']}", headers=ADMIN_HEADERS)
    assert r.status_code == 403
    body = r.json()
    assert body["title"] == "Forbidden"
    assert "自己" in body["detail"]


async def test_delete_last_admin_conflict(client: AsyncClient) -> None:
    """Deleting the only admin must return 409 Conflict."""
    # Create a second admin, delete the original admin, then try to delete
    # the second admin (now the last one).
    payload = {
        "name": "Second Admin",
        "email": "second-admin@example.com",
        "password": "AdminPass123",
        "role": "admin",
    }
    created = (await client.post(API, json=payload, headers=ADMIN_HEADERS)).json()

    # Delete Alice (the original admin) — should succeed since there are 2 admins
    members = (await client.get(API, headers=ADMIN_HEADERS)).json()["items"]
    alice = next(m for m in members if m["name"] == "Alice Admin")
    r = await client.delete(f"{API}/{alice['id']}", headers=ADMIN_HEADERS)
    assert r.status_code == 200

    # Now the second admin is the last admin. Try to delete them.
    r = await client.delete(f"{API}/{created['id']}", headers=ADMIN_HEADERS)
    assert r.status_code == 409
    body = r.json()
    assert body["title"] == "Conflict"
    assert "管理员" in body["detail"]


async def test_demote_last_admin_conflict(client: AsyncClient) -> None:
    """Demoting the only admin to a non-admin role must return 409."""
    members = (await client.get(API, headers=ADMIN_HEADERS)).json()["items"]
    alice = next(m for m in members if m["name"] == "Alice Admin")
    r = await client.put(
        f"{API}/{alice['id']}",
        json={"role": "developer"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 409
    body = r.json()
    assert body["title"] == "Conflict"
    assert "管理员" in body["detail"]


async def test_demote_admin_when_other_admin_exists(client: AsyncClient) -> None:
    """Demoting an admin should succeed when another admin exists."""
    # Create a second admin
    payload = {
        "name": "Second Admin",
        "email": "second-admin2@example.com",
        "password": "AdminPass123",
        "role": "admin",
    }
    await client.post(API, json=payload, headers=ADMIN_HEADERS)

    # Demote Alice to developer — should succeed
    members = (await client.get(API, headers=ADMIN_HEADERS)).json()["items"]
    alice = next(m for m in members if m["name"] == "Alice Admin")
    r = await client.put(
        f"{API}/{alice['id']}",
        json={"role": "developer"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["role"] == "developer"
