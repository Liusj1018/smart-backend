"""Business logic for member operations backed by PostgreSQL."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.team_member import TeamMember
from app.db.models.user import User
from app.exceptions import (
    ConflictError,
    NotFoundError,
)
from app.models.member import Member, Role
from app.schemas.common import PaginationParams


def _to_member(tm: TeamMember) -> Member:
    """Convert a TeamMember ORM object (with user eagerly loaded) to domain Member."""
    return Member(
        id=str(tm.id),
        team_id=str(tm.team_id),
        name=tm.user.name,
        email=tm.user.email,
        role=Role(tm.role),
        github_username=tm.user.github_username,
        created_at=tm.created_at,
        updated_at=tm.updated_at,
    )


async def list_members(
    db: AsyncSession,
    team_id: str,
    pagination: PaginationParams,
    role: str | None = None,
    name: str | None = None,
) -> tuple[list[Member], int]:
    """Return a paginated, optionally filtered list of team members."""
    tid = UUID(team_id)
    conditions = [TeamMember.team_id == tid]

    if role is not None:
        conditions.append(TeamMember.role == role)
    if name is not None:
        conditions.append(User.name.ilike(f"%{name}%"))

    # Count
    count_q = (
        select(func.count())
        .select_from(TeamMember)
        .join(User, TeamMember.user_id == User.id)
        .where(*conditions)
    )
    total = (await db.execute(count_q)).scalar_one()

    # Data
    q = (
        select(TeamMember)
        .join(User, TeamMember.user_id == User.id)
        .where(*conditions)
        .options(selectinload(TeamMember.user))
        .order_by(TeamMember.joined_at.asc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    result = await db.execute(q)
    items = [_to_member(tm) for tm in result.scalars().unique().all()]
    return items, total


async def get_member(db: AsyncSession, team_id: str, member_id: str) -> Member:
    """Fetch a single member by ID within the team."""
    try:
        tid = UUID(team_id)
        mid = UUID(member_id)
    except ValueError as exc:
        raise NotFoundError("成员不存在") from exc
    result = await db.execute(
        select(TeamMember)
        .where(TeamMember.id == mid, TeamMember.team_id == tid)
        .options(selectinload(TeamMember.user))
    )
    tm = result.scalar_one_or_none()
    if tm is None:
        raise NotFoundError("成员不存在")
    return _to_member(tm)


async def create_member(
    db: AsyncSession,
    team_id: str,
    name: str,
    email: str,
    role: Role,
    github_username: str | None = None,
) -> Member:
    """Create a new user and add them to the team."""
    tid = UUID(team_id)

    # Check for duplicate email
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("该邮箱已被使用")

    user = User(
        name=name,
        email=email,
        password_hash="!",
        github_username=github_username,
    )
    db.add(user)
    await db.flush()

    tm = TeamMember(team_id=tid, user_id=user.id, role=role.value)
    db.add(tm)
    await db.flush()
    await db.refresh(tm)

    return _to_member(tm)


async def update_member(
    db: AsyncSession,
    team_id: str,
    member_id: str,
    name: str | None = None,
    email: str | None = None,
    role: Role | None = None,
    github_username: str | None = None,
) -> Member:
    """Update a member's information."""
    try:
        tid = UUID(team_id)
        mid = UUID(member_id)
    except ValueError as exc:
        raise NotFoundError("成员不存在") from exc

    result = await db.execute(
        select(TeamMember)
        .where(TeamMember.id == mid, TeamMember.team_id == tid)
        .options(selectinload(TeamMember.user))
    )
    tm = result.scalar_one_or_none()
    if tm is None:
        raise NotFoundError("成员不存在")

    if role is not None:
        tm.role = role.value
    if name is not None:
        tm.user.name = name
    if email is not None:
        tm.user.email = email
    if github_username is not None:
        tm.user.github_username = github_username

    await db.flush()
    await db.refresh(tm)
    return _to_member(tm)


async def delete_member(db: AsyncSession, team_id: str, member_id: str) -> None:
    """Delete a member."""
    try:
        tid = UUID(team_id)
        mid = UUID(member_id)
    except ValueError as exc:
        raise NotFoundError("成员不存在") from exc
    result = await db.execute(
        delete(TeamMember).where(TeamMember.id == mid, TeamMember.team_id == tid)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise NotFoundError("成员不存在")
