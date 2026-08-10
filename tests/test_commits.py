"""Tests for commit query and workload endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import ADMIN_HEADERS, BETA_HEADERS, TEAM_ALPHA, TEAM_BETA

pytestmark = pytest.mark.anyio

API = "/api/v1/commits"


# ---------- list commits ----------

async def test_list_commits_returns_seed_data(client: AsyncClient) -> None:
    r = await client.get(API, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert body["page"] == 1
    assert len(body["items"]) == body["total"]
    assert "X-Trace-Id" in r.headers


async def test_list_commits_pagination(client: AsyncClient) -> None:
    r = await client.get(API, params={"page": 1, "page_size": 2}, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total_pages"] >= 1


async def test_list_commits_filter_by_member(client: AsyncClient) -> None:
    members = (await client.get("/api/v1/members", headers=ADMIN_HEADERS)).json()["items"]
    dev_id = next(m["id"] for m in members if m["role"] == "developer")
    r = await client.get(API, params={"member_id": dev_id}, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert all(c["member_id"] == dev_id for c in body["items"])


async def test_list_commits_filter_by_repository(client: AsyncClient) -> None:
    r = await client.get(
        API,
        params={"repository": "smart-commit-backend"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert all(c["repository"] == "smart-commit-backend" for c in body["items"])


async def test_list_commits_invalid_page(client: AsyncClient) -> None:
    r = await client.get(API, params={"page": -1}, headers=ADMIN_HEADERS)
    assert r.status_code == 422
    assert r.json()["trace_id"]


async def test_list_commits_missing_team_header(client: AsyncClient) -> None:
    # Without a token, auth dependency returns 401 before team header is checked.
    r = await client.get(API)
    assert r.status_code == 401


# ---------- tenant isolation ----------

async def test_commits_tenant_isolation(client: AsyncClient) -> None:
    r_alpha = await client.get(API, headers=ADMIN_HEADERS)
    r_beta = await client.get(API, headers=BETA_HEADERS)
    alpha_ids = {c["id"] for c in r_alpha.json()["items"]}
    beta_ids = {c["id"] for c in r_beta.json()["items"]}
    assert alpha_ids.isdisjoint(beta_ids)


# ---------- commit detail ----------

async def test_get_commit_detail(client: AsyncClient) -> None:
    commits = (await client.get(API, headers=ADMIN_HEADERS)).json()["items"]
    cid = commits[0]["id"]
    r = await client.get(f"{API}/{cid}", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == cid
    assert body["team_id"] == str(TEAM_ALPHA)
    assert "sha" in body
    assert "message" in body
    assert "ai_percentage" in body
    assert 0 <= body["ai_percentage"] <= 100


async def test_list_commits_includes_ai_percentage(client: AsyncClient) -> None:
    r = await client.get(API, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 0
    for c in items:
        assert "ai_percentage" in c
        assert 0 <= c["ai_percentage"] <= 100


async def test_get_commit_not_found(client: AsyncClient) -> None:
    r = await client.get(f"{API}/nonexistent-id", headers=ADMIN_HEADERS)
    assert r.status_code == 404
    assert r.json()["title"] == "Not Found"


async def test_get_commit_other_team_not_found(client: AsyncClient) -> None:
    beta_commits = (await client.get(API, headers=BETA_HEADERS)).json()["items"]
    bid = beta_commits[0]["id"]
    r = await client.get(f"{API}/{bid}", headers=ADMIN_HEADERS)
    assert r.status_code == 404


# ---------- workload ----------

async def test_get_workload(client: AsyncClient) -> None:
    members = (await client.get("/api/v1/members", headers=ADMIN_HEADERS)).json()["items"]
    dev_id = next(m["id"] for m in members if m["role"] == "developer")
    r = await client.get(f"{API}/workload/{dev_id}", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["member_id"] == dev_id
    assert body["total_commits"] > 0
    assert body["total_lines_added"] > 0
    assert "period_start" in body
    assert "period_end" in body


async def test_get_workload_with_date_range(client: AsyncClient) -> None:
    members = (await client.get("/api/v1/members", headers=ADMIN_HEADERS)).json()["items"]
    dev_id = next(m["id"] for m in members if m["role"] == "developer")
    r = await client.get(
        f"{API}/workload/{dev_id}",
        params={"start_date": "2020-01-01T00:00:00Z", "end_date": "2030-01-01T00:00:00Z"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["total_commits"] > 0


async def test_list_commits_filter_by_date_range(client: AsyncClient) -> None:
    """Date range filtering: narrow range should return fewer or zero results."""
    # future range → no commits
    r = await client.get(
        API,
        params={"start_date": "2030-01-01T00:00:00Z", "end_date": "2031-01-01T00:00:00Z"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0

    # past range ending before seed commits → filtered out by end_date
    r2 = await client.get(
        API,
        params={"end_date": "2000-01-01T00:00:00Z"},
        headers=ADMIN_HEADERS,
    )
    assert r2.status_code == 200
    assert r2.json()["total"] == 0


async def test_get_workload_viewer_member(client: AsyncClient) -> None:
    """Viewer has no commits → workload should be zero."""
    members = (await client.get("/api/v1/members", headers=ADMIN_HEADERS)).json()["items"]
    viewer_id = next(m["id"] for m in members if m["role"] == "viewer")
    r = await client.get(f"{API}/workload/{viewer_id}", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total_commits"] == 0
    assert body["total_lines_added"] == 0
    assert body["total_lines_deleted"] == 0


# ---------- row-level security (S7) ----------

async def test_cross_team_workload_returns_404(client: AsyncClient) -> None:
    """Accessing another team's member workload returns 404 (not 403)."""
    beta_members = (await client.get("/api/v1/members", headers=BETA_HEADERS)).json()["items"]
    beta_member_id = beta_members[0]["id"]
    r = await client.get(f"{API}/workload/{beta_member_id}", headers=ADMIN_HEADERS)
    assert r.status_code == 404
    body = r.json()
    assert body["title"] == "Not Found"
    assert body["trace_id"]


async def test_cross_team_commit_detail_404(client: AsyncClient) -> None:
    """Team-alpha user accessing team-beta commit detail gets 404."""
    beta_commits = (await client.get(API, headers=BETA_HEADERS)).json()["items"]
    beta_commit_id = beta_commits[0]["id"]
    r = await client.get(f"{API}/{beta_commit_id}", headers=ADMIN_HEADERS)
    assert r.status_code == 404
    assert r.json()["trace_id"]


async def test_x_team_id_header_ignored_for_commits(client: AsyncClient) -> None:
    """Forging X-Team-Id header must not change tenant scope for commits."""
    headers = {**ADMIN_HEADERS, "X-Team-Id": str(TEAM_BETA)}
    r = await client.get(API, headers=headers)
    assert r.status_code == 200
    alpha_ids = {c["id"] for c in r.json()["items"]}
    beta_commits = (await client.get(API, headers=BETA_HEADERS)).json()["items"]
    beta_ids = {c["id"] for c in beta_commits}
    assert alpha_ids.isdisjoint(beta_ids)


async def test_cross_team_member_filter_returns_empty(client: AsyncClient) -> None:
    """Filtering commits by a member_id from another team returns empty results."""
    beta_members = (await client.get("/api/v1/members", headers=BETA_HEADERS)).json()["items"]
    beta_member_id = beta_members[0]["id"]
    r = await client.get(
        API, params={"member_id": beta_member_id}, headers=ADMIN_HEADERS
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0
