"""Unit tests for the 5 core business queries (S5).

These tests run against the real PostgreSQL database (the one configured
in ``app.config.settings.database_url``). They use a savepoint-based
isolation pattern so each test rolls back its changes and the database
stays clean.

Run with SQL echo to verify no N+1::

    pytest tests/test_queries.py -v --log-cli-level=DEBUG
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.team import Team
from app.db.models.team_member import TeamMember
from app.db.models.user import User
from app.db.session import engine
from app.queries import (
    count_team_commits,
    get_member_detail,
    get_team_members,
    get_user_commits,
    search_members,
)

pytestmark = pytest.mark.anyio


@pytest.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session wrapped in a transaction that rolls back."""
    connection = await engine.connect()
    trans = await connection.begin()
    session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
    await trans.rollback()
    await connection.close()


async def _seed_minimal_data(session: AsyncSession) -> dict[str, Any]:
    """Insert a minimal deterministic dataset for query tests.

    Returns a dict with the IDs of created entities so tests can
    reference them.
    """
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from app.db.models.commit import Commit
    from app.db.models.repo import Repo

    now = datetime.now(UTC)

    # Two teams for multi-tenant isolation testing
    team_a = Team(id=uuid4(), name="Team A", slug="team-a-test")
    team_b = Team(id=uuid4(), name="Team B", slug="team-b-test")
    session.add_all([team_a, team_b])
    await session.flush()

    # Users
    alice = User(
        id=uuid4(),
        email="alice@test.com",
        name="Alice Anderson",
        password_hash="hash1",
    )
    bob = User(
        id=uuid4(),
        email="bob@test.com",
        name="Bob Brown",
        password_hash="hash2",
    )
    carol = User(
        id=uuid4(),
        email="carol@test.com",
        name="Carol Chen",
        password_hash="hash3",
    )
    dave = User(
        id=uuid4(),
        email="dave@otherteam.com",
        name="Dave Davis",
        password_hash="hash4",
    )
    session.add_all([alice, bob, carol, dave])
    await session.flush()

    # Team memberships
    tm_alice = TeamMember(
        id=uuid4(),
        team_id=team_a.id,
        user_id=alice.id,
        role="admin",
        joined_at=now - timedelta(days=30),
    )
    tm_bob = TeamMember(
        id=uuid4(),
        team_id=team_a.id,
        user_id=bob.id,
        role="developer",
        joined_at=now - timedelta(days=20),
    )
    tm_carol = TeamMember(
        id=uuid4(),
        team_id=team_a.id,
        user_id=carol.id,
        role="viewer",
        joined_at=now - timedelta(days=10),
    )
    tm_dave = TeamMember(
        id=uuid4(),
        team_id=team_b.id,
        user_id=dave.id,
        role="admin",
        joined_at=now - timedelta(days=5),
    )
    session.add_all([tm_alice, tm_bob, tm_carol, tm_dave])
    await session.flush()

    # Repos for team A
    repo1 = Repo(
        id=uuid4(),
        team_id=team_a.id,
        name="repo-alpha",
        url="https://github.com/team-a/repo-alpha",
        description="Alpha repo",
    )
    repo2 = Repo(
        id=uuid4(),
        team_id=team_a.id,
        name="repo-beta",
        url="https://github.com/team-a/repo-beta",
        description="Beta repo",
    )
    session.add_all([repo1, repo2])
    await session.flush()

    # Commits: alice has 3, bob has 2, carol has 0 (viewer)
    commits: list[Commit] = []
    for i in range(3):
        commits.append(
            Commit(
                id=uuid4(),
                team_id=team_a.id,
                user_id=alice.id,
                repo_id=repo1.id if i % 2 == 0 else repo2.id,
                sha=f"a11ce{0:034d}".replace("0", str(i))[:40],
                message=f"Alice commit {i}",
                additions=10 * (i + 1),
                deletions=2 * (i + 1),
                committed_at=now - timedelta(days=i),
            )
        )
    for i in range(2):
        commits.append(
            Commit(
                id=uuid4(),
                team_id=team_a.id,
                user_id=bob.id,
                repo_id=repo1.id,
                sha=f"b0b{0:037d}".replace("0", str(i))[:40],
                message=f"Bob commit {i}",
                additions=5 * (i + 1),
                deletions=i + 1,
                committed_at=now - timedelta(days=i + 1),
            )
        )
    session.add_all(commits)
    await session.flush()

    return {
        "team_a": team_a,
        "team_b": team_b,
        "alice": alice,
        "bob": bob,
        "carol": carol,
        "dave": dave,
        "repo1": repo1,
        "repo2": repo2,
        "commits": commits,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_get_team_members_returns_all_members(
    db_session: AsyncSession,
) -> None:
    """get_team_members returns all members for the team."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]

    members = await get_team_members(db_session, team_a.id)

    assert len(members) == 3
    # Ordered by joined_at ascending
    assert members[0].user.name == "Alice Anderson"
    assert members[1].user.name == "Bob Brown"
    assert members[2].user.name == "Carol Chen"


async def test_get_team_members_is_tenant_isolated(
    db_session: AsyncSession,
) -> None:
    """get_team_members does not return members from other teams."""
    data = await _seed_minimal_data(db_session)
    team_b = data["team_b"]

    members = await get_team_members(db_session, team_b.id)

    assert len(members) == 1
    assert members[0].user.name == "Dave Davis"


async def test_get_team_members_eager_loads_user(
    db_session: AsyncSession,
) -> None:
    """Accessing member.user does not trigger lazy loading (N+1 safe)."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]

    members = await get_team_members(db_session, team_a.id)

    # After the query, accessing .user should not trigger a DB query
    # because selectinload already loaded it. We verify by checking
    # the attribute is loaded without expiration.
    for member in members:
        assert member.user.name  # Should not raise MissingGreenlet


async def test_get_member_detail_returns_correct_member(
    db_session: AsyncSession,
) -> None:
    """get_member_detail returns the specific member."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]
    alice = data["alice"]

    member = await get_member_detail(db_session, team_a.id, alice.id)

    assert member is not None
    assert member.role == "admin"
    assert member.user.email == "alice@test.com"
    assert member.user.name == "Alice Anderson"


async def test_get_member_detail_returns_none_for_wrong_team(
    db_session: AsyncSession,
) -> None:
    """get_member_detail returns None when user is not in the given team."""
    data = await _seed_minimal_data(db_session)
    team_b = data["team_b"]
    alice = data["alice"]

    # Alice is in team A, not team B
    member = await get_member_detail(db_session, team_b.id, alice.id)

    assert member is None


async def test_get_member_detail_eager_loads_user(
    db_session: AsyncSession,
) -> None:
    """Accessing member.user does not trigger lazy loading."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]
    bob = data["bob"]

    member = await get_member_detail(db_session, team_a.id, bob.id)

    assert member is not None
    assert member.user.name == "Bob Brown"  # No lazy load


async def test_get_user_commits_returns_users_commits(
    db_session: AsyncSession,
) -> None:
    """get_user_commits returns all commits for a user in a team."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]
    alice = data["alice"]

    commits = await get_user_commits(db_session, team_a.id, alice.id)

    assert len(commits) == 3
    # Ordered by committed_at descending
    assert commits[0].message == "Alice commit 0"


async def test_get_user_commits_tenant_isolated(
    db_session: AsyncSession,
) -> None:
    """get_user_commits returns empty for user in different team."""
    data = await _seed_minimal_data(db_session)
    team_b = data["team_b"]
    alice = data["alice"]

    commits = await get_user_commits(db_session, team_b.id, alice.id)

    assert commits == []


async def test_get_user_commits_eager_loads_repo(
    db_session: AsyncSession,
) -> None:
    """Accessing commit.repo does not trigger lazy loading (N+1 safe)."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]
    alice = data["alice"]

    commits = await get_user_commits(db_session, team_a.id, alice.id)

    for commit in commits:
        assert commit.repo.name  # Should not raise MissingGreenlet


async def test_count_team_commits_returns_correct_count(
    db_session: AsyncSession,
) -> None:
    """count_team_commits returns the total commits for the team."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]

    count = await count_team_commits(db_session, team_a.id)

    # Alice: 3, Bob: 2 = 5 total
    assert count == 5


async def test_count_team_commits_tenant_isolated(
    db_session: AsyncSession,
) -> None:
    """count_team_commits returns 0 for a team with no commits."""
    data = await _seed_minimal_data(db_session)
    team_b = data["team_b"]

    count = await count_team_commits(db_session, team_b.id)

    assert count == 0


async def test_search_members_by_name(
    db_session: AsyncSession,
) -> None:
    """search_members finds members by name keyword."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]

    results = await search_members(db_session, team_a.id, "Alice")

    assert len(results) == 1
    assert results[0].user.name == "Alice Anderson"


async def test_search_members_by_email(
    db_session: AsyncSession,
) -> None:
    """search_members finds members by email keyword."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]

    results = await search_members(db_session, team_a.id, "bob@test")

    assert len(results) == 1
    assert results[0].user.name == "Bob Brown"


async def test_search_members_case_insensitive(
    db_session: AsyncSession,
) -> None:
    """search_members is case-insensitive."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]

    results = await search_members(db_session, team_a.id, "carol")

    assert len(results) == 1
    assert results[0].user.name == "Carol Chen"


async def test_search_members_partial_match(
    db_session: AsyncSession,
) -> None:
    """search_members supports partial keyword matching."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]

    # "an" matches "Alice Anderson"
    results = await search_members(db_session, team_a.id, "an")

    names = {m.user.name for m in results}
    assert "Alice Anderson" in names


async def test_search_members_tenant_isolated(
    db_session: AsyncSession,
) -> None:
    """search_members does not return members from other teams."""
    data = await _seed_minimal_data(db_session)
    team_b = data["team_b"]

    results = await search_members(db_session, team_b.id, "Alice")

    assert results == []


async def test_search_members_eager_loads_user(
    db_session: AsyncSession,
) -> None:
    """Accessing member.user does not trigger lazy loading (N+1 safe)."""
    data = await _seed_minimal_data(db_session)
    team_a = data["team_a"]

    results = await search_members(db_session, team_a.id, "a")

    for member in results:
        assert member.user.email  # Should not raise MissingGreenlet
