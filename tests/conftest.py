"""Shared test fixtures.

Tests run against the real PostgreSQL database using a connection-level
transaction that is rolled back after each test, ensuring test isolation
without polluting the database.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# On Windows, psycopg async requires SelectorEventLoop (not ProactorEventLoop)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.jwt_tokens import create_access_token
from app.core.security import hash_password
from app.db.models.commit import Commit
from app.db.models.repo import Repo
from app.db.models.team import Team
from app.db.models.team_member import TeamMember
from app.db.models.user import User
from app.db.session import engine, get_db
from app.main import create_app

# Default password for all seed users
SEED_PASSWORD = "TestPass123"
SEED_PASSWORD_HASH = hash_password(SEED_PASSWORD)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEAM_ALPHA = UUID("11111111-1111-1111-1111-111111111111")
TEAM_BETA = UUID("22222222-2222-2222-2222-222222222222")

# Fixed user IDs so JWT tokens can be generated deterministically
USER_ALICE = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_BOB = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_CAROL = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
USER_DAVE = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
USER_EVE = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _auth_headers(team_id: UUID, user_id: UUID, role: str) -> dict[str, str]:
    """Build request headers with JWT Bearer token.

    The token embeds ``team_id`` and ``role`` so the server can establish
    the tenant context without trusting client-supplied headers.
    """
    token = create_access_token(str(user_id), role, str(team_id))
    return {"Authorization": f"Bearer {token}"}


ADMIN_HEADERS = _auth_headers(TEAM_ALPHA, USER_ALICE, "admin")
DEV_HEADERS = _auth_headers(TEAM_ALPHA, USER_BOB, "developer")
VIEWER_HEADERS = _auth_headers(TEAM_ALPHA, USER_DAVE, "viewer")
BETA_HEADERS = _auth_headers(TEAM_BETA, USER_EVE, "admin")


# ---------------------------------------------------------------------------
# Database session with transaction rollback
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a session wrapped in a transaction that rolls back."""
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


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------


async def _seed_data(session: AsyncSession) -> dict[str, Any]:
    """Insert deterministic test data and return entity references."""
    now = datetime.now(UTC)

    # Teams
    team_alpha = Team(
        id=TEAM_ALPHA,
        name="Team Alpha",
        slug="team-alpha",
    )
    team_beta = Team(
        id=TEAM_BETA,
        name="Team Beta",
        slug="team-beta",
    )
    session.add_all([team_alpha, team_beta])
    await session.flush()

    # Users for team alpha
    users = []
    user_data = [
        ("Alice Admin", "alice@alpha.com", "alice-gh", "admin"),
        ("Bob Developer", "bob@alpha.com", "bob-gh", "developer"),
        ("Carol Developer", "carol@alpha.com", "carol-gh", "developer"),
        ("Dave Viewer", "dave@alpha.com", None, "viewer"),
    ]
    user_ids = [USER_ALICE, USER_BOB, USER_CAROL, USER_DAVE]
    for (name, email, gh, role), uid in zip(user_data, user_ids, strict=True):
        u = User(
            id=uid,
            name=name,
            email=email,
            password_hash=SEED_PASSWORD_HASH,
            github_username=gh,
        )
        users.append((u, role))
        session.add(u)

    # User for team beta
    beta_user = User(
        id=USER_EVE,
        name="Eve Beta",
        email="eve@beta.com",
        password_hash=SEED_PASSWORD_HASH,
        github_username="eve-gh",
    )
    session.add(beta_user)
    await session.flush()

    # Team members
    members = []
    for u, role in users:
        tm = TeamMember(
            id=uuid4(),
            team_id=team_alpha.id,
            user_id=u.id,
            role=role,
            joined_at=now - timedelta(days=30),
        )
        members.append((tm, u, role))
        session.add(tm)

    beta_tm = TeamMember(
        id=uuid4(),
        team_id=team_beta.id,
        user_id=beta_user.id,
        role="admin",
        joined_at=now - timedelta(days=10),
    )
    session.add(beta_tm)
    await session.flush()

    # Repos
    repo1 = Repo(
        id=uuid4(),
        team_id=team_alpha.id,
        name="smart-commit-backend",
        url="https://github.com/alpha/smart-commit-backend",
        description="Main backend repo",
    )
    repo2 = Repo(
        id=uuid4(),
        team_id=team_alpha.id,
        name="smart-commit-frontend",
        url="https://github.com/alpha/smart-commit-frontend",
        description="Frontend repo",
    )
    session.add_all([repo1, repo2])
    await session.flush()

    # Beta repo + commit (for tenant isolation tests)
    beta_repo = Repo(
        id=uuid4(),
        team_id=team_beta.id,
        name="beta-service",
        url="https://github.com/beta/beta-service",
        description="Beta team repo",
    )
    session.add(beta_repo)
    await session.flush()

    beta_commit = Commit(
        id=uuid4(),
        team_id=team_beta.id,
        user_id=beta_user.id,
        repo_id=beta_repo.id,
        sha="e" + "b" * 39,
        message="Eve beta commit",
        additions=42,
        deletions=7,
        ai_percentage=20,
        committed_at=now - timedelta(days=1),
    )
    session.add(beta_commit)
    await session.flush()

    # Commits: Bob (developer) has 3, Carol (developer) has 2
    bob = members[1][1]  # Bob Developer
    carol = members[2][1]  # Carol Developer

    commits: list[Commit] = []
    bob_ai = [30, 0, 75]
    for i in range(3):
        commits.append(
            Commit(
                id=uuid4(),
                team_id=team_alpha.id,
                user_id=bob.id,
                repo_id=repo1.id if i % 2 == 0 else repo2.id,
                sha=f"bob{0:037d}".replace("0", str(i + 1))[:40],
                message=f"Bob commit #{i + 1}",
                additions=10 * (i + 1),
                deletions=2 * (i + 1),
                ai_percentage=bob_ai[i],
                committed_at=now - timedelta(days=i),
            )
        )
    carol_ai = [50, 100]
    for i in range(2):
        commits.append(
            Commit(
                id=uuid4(),
                team_id=team_alpha.id,
                user_id=carol.id,
                repo_id=repo1.id,
                sha=f"carol{0:035d}".replace("0", str(i + 1))[:40],
                message=f"Carol commit #{i + 1}",
                additions=5 * (i + 1),
                deletions=i + 1,
                ai_percentage=carol_ai[i],
                committed_at=now - timedelta(days=i + 1),
            )
        )
    session.add_all(commits)
    await session.flush()

    return {
        "team_alpha": team_alpha,
        "team_beta": team_beta,
        "members": members,
        "beta_tm": beta_tm,
        "repos": [repo1, repo2],
        "commits": commits,
    }


# ---------------------------------------------------------------------------
# HTTP client with DB override
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with get_db overridden to use the transactional session."""
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    # Seed data within the same transaction
    await _seed_data(db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
