"""Core business queries for the Smart Commit data layer.

All queries are multi-tenant safe: every function requires a ``team_id``
and filters by it. List queries use ``selectinload`` to eagerly load
related data and avoid N+1 queries.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.commit import Commit
from app.db.models.repo import Repo
from app.db.models.team_member import TeamMember
from app.db.models.user import User


async def get_team_members(
    session: AsyncSession,
    team_id: UUID,
) -> list[TeamMember]:
    """Return all team members for a given team.

    Eagerly loads the associated ``user`` so accessing ``member.user``
    does not trigger additional queries (N+1 safe).
    """
    stmt = (
        select(TeamMember)
        .where(TeamMember.team_id == team_id)
        .options(selectinload(TeamMember.user))
        .order_by(TeamMember.joined_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_member_detail(
    session: AsyncSession,
    team_id: UUID,
    user_id: UUID,
) -> TeamMember | None:
    """Return a single team member's detail.

    Eagerly loads the associated ``user``.
    """
    stmt = (
        select(TeamMember)
        .where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
        )
        .options(selectinload(TeamMember.user))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_commits(
    session: AsyncSession,
    team_id: UUID,
    user_id: UUID,
) -> list[Commit]:
    """Return all commits made by a user within a team.

    Eagerly loads the associated ``repo`` so accessing ``commit.repo``
    does not trigger additional queries (N+1 safe).
    """
    stmt = (
        select(Commit)
        .where(
            Commit.team_id == team_id,
            Commit.user_id == user_id,
        )
        .options(selectinload(Commit.repo))
        .order_by(Commit.committed_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_team_commits(
    session: AsyncSession,
    team_id: UUID,
) -> int:
    """Return the total number of commits in a team."""
    stmt = select(func.count()).select_from(Commit).where(Commit.team_id == team_id)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def search_members(
    session: AsyncSession,
    team_id: UUID,
    keyword: str,
) -> list[TeamMember]:
    """Search team members by user name or email.

    Eagerly loads the associated ``user`` so accessing ``member.user``
    does not trigger additional queries (N+1 safe).
    """
    pattern = f"%{keyword}%"
    stmt = (
        select(TeamMember)
        .join(User, TeamMember.user_id == User.id)
        .where(
            TeamMember.team_id == team_id,
            (User.name.ilike(pattern)) | (User.email.ilike(pattern)),
        )
        .options(selectinload(TeamMember.user))
        .order_by(TeamMember.joined_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_team_commits(
    db: AsyncSession,
    team_id: UUID,
    *,
    member_id: UUID | None = None,
    repository: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Commit], int]:
    """Return paginated commits for a team with optional filters.

    Filters:
        member_id: filter by author user ID
        repository: filter by repo name (case-insensitive partial match)
        start_date: only commits on or after this datetime
        end_date: only commits on or before this datetime

    Returns:
        Tuple of (list of Commit ORM objects, total count)
    """
    conditions = [Commit.team_id == team_id]

    if member_id is not None:
        conditions.append(Commit.user_id == member_id)
    if start_date is not None:
        conditions.append(Commit.committed_at >= start_date)
    if end_date is not None:
        conditions.append(Commit.committed_at <= end_date)

    # Count query
    count_q = select(func.count(func.distinct(Commit.id))).select_from(Commit)
    if repository is not None:
        count_q = count_q.join(Repo, Commit.repo_id == Repo.id).where(
            Repo.name.ilike(f"%{repository}%")
        )
    count_q = count_q.where(*conditions)
    total = (await db.execute(count_q)).scalar_one()

    # Data query with eager loading
    q = (
        select(Commit)
        .options(
            selectinload(Commit.user),
            selectinload(Commit.repo),
        )
        .where(*conditions)
        .order_by(Commit.committed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if repository is not None:
        q = q.join(Repo, Commit.repo_id == Repo.id).where(
            Repo.name.ilike(f"%{repository}%")
        )

    result = await db.execute(q)
    items = list(result.scalars().unique().all())
    return items, total
