"""In-memory data store with seed data for development."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.commit import Commit, Workload
from app.models.member import Member, Role

# ---------------------------------------------------------------------------
# In-memory stores keyed by team_id for multi-tenant isolation
# ---------------------------------------------------------------------------

# team_id -> {member_id -> Member}
_members: dict[str, dict[str, Member]] = {}

# team_id -> {commit_id -> Commit}
_commits: dict[str, dict[str, Commit]] = {}


def reset() -> None:
    """Clear all data (used by tests)."""
    _members.clear()
    _commits.clear()


def seed() -> None:
    """Re-populate sample data (used by tests after reset)."""
    _seed()


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------


def members_store(team_id: str) -> dict[str, Member]:
    """Return (and lazily create) the member dict for a team."""
    return _members.setdefault(team_id, {})


def commits_store(team_id: str) -> dict[str, Commit]:
    """Return (and lazily create) the commit dict for a team."""
    return _commits.setdefault(team_id, {})


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------


def _seed() -> None:
    """Populate sample data for two teams."""
    now = datetime.now(UTC)

    teams: dict[str, list[tuple[str, str, Role, str | None]]] = {
        "team-alpha": [
            ("Alice Zhang", "alice@example.com", Role.admin, "alicez"),
            ("Bob Li", "bob@example.com", Role.developer, "bobl"),
            ("Carol Wang", "carol@example.com", Role.developer, "carolw"),
            ("Dave Chen", "dave@example.com", Role.viewer, None),
        ],
        "team-beta": [
            ("Eve Liu", "eve@example.com", Role.admin, "evel"),
            ("Frank Zhao", "frank@example.com", Role.developer, "frankz"),
            ("Grace Sun", "grace@example.com", Role.developer, "graces"),
        ],
    }

    for team_id, people in teams.items():
        m_store = members_store(team_id)
        c_store = commits_store(team_id)

        member_ids: list[str] = []
        for name, email, role, gh in people:
            mid = str(uuid4())
            member_ids.append(mid)
            m_store[mid] = Member(
                id=mid,
                team_id=team_id,
                name=name,
                email=email,
                role=role,
                github_username=gh,
                created_at=now - timedelta(days=30),
                updated_at=now - timedelta(days=1),
            )

        # Seed commits for developers
        repos = ["smart-commit-backend", "smart-commit-frontend"]
        for idx, mid in enumerate(member_ids):
            member = m_store[mid]
            if member.role == Role.viewer:
                continue
            for n in range(3):
                cid = str(uuid4())
                c_store[cid] = Commit(
                    id=cid,
                    team_id=team_id,
                    member_id=mid,
                    sha=f"{uuid4().hex[:7]}{idx}{n}",
                    message=f"feat: sample commit {n + 1} by {member.name}",
                    repository=repos[n % len(repos)],
                    branch="main",
                    lines_added=10 * (n + 1) * (idx + 1),
                    lines_deleted=2 * (n + 1) * (idx + 1),
                    committed_at=now - timedelta(days=n, hours=idx),
                )


_seed()


__all__ = [
    "Commit",
    "Member",
    "Role",
    "Workload",
    "commits_store",
    "members_store",
    "reset",
    "seed",
]
