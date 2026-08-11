"""Business logic for member operations backed by PostgreSQL."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.db.models.team_member import TeamMember
from app.db.models.user import User
from app.exceptions import (
    ConflictError,
    ForbiddenError,
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
    password: str,
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
        password_hash=hash_password(password),
        github_username=github_username,
    )
    db.add(user)
    await db.flush()

    tm = TeamMember(team_id=tid, user_id=user.id, role=role.value)
    db.add(tm)
    await db.flush()
    await db.refresh(tm)

    return _to_member(tm)


async def _count_admins(db: AsyncSession, team_id: UUID) -> int:
    """Return the number of admin members in a team."""
    count_q = (
        select(func.count())
        .select_from(TeamMember)
        .where(TeamMember.team_id == team_id, TeamMember.role == "admin")
    )
    return (await db.execute(count_q)).scalar_one()


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

    # Prevent demoting the last admin
    if role is not None and role.value != "admin" and tm.role == "admin":
        admin_count = await _count_admins(db, tid)
        if admin_count <= 1:
            raise ConflictError("团队必须至少保留一名管理员")

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


async def delete_member(
    db: AsyncSession,
    team_id: str,
    member_id: str,
    current_user_id: str | None = None,
) -> None:
    """Delete a member.

    Args:
        db: Database session.
        team_id: The tenant UUID.
        member_id: The TeamMember UUID to delete.
        current_user_id: The User UUID of the caller — used to prevent
            self-deletion.
    """
    try:
        tid = UUID(team_id)
        mid = UUID(member_id)
    except ValueError as exc:
        raise NotFoundError("成员不存在") from exc

    # Fetch the member first to check role and user_id
    result = await db.execute(
        select(TeamMember)
        .where(TeamMember.id == mid, TeamMember.team_id == tid)
        .options(selectinload(TeamMember.user))
    )
    tm = result.scalar_one_or_none()
    if tm is None:
        raise NotFoundError("成员不存在")

    # Prevent self-deletion
    if current_user_id is not None and str(tm.user_id) == current_user_id:
        raise ForbiddenError("不能删除自己的账号")

    # Prevent deleting the last admin
    if tm.role == "admin":
        admin_count = await _count_admins(db, tid)
        if admin_count <= 1:
            raise ConflictError("团队必须至少保留一名管理员")

    await db.execute(
        delete(TeamMember).where(TeamMember.id == mid, TeamMember.team_id == tid)
    )
