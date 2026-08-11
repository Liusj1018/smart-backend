"""HTTP API for team member management.

All endpoints are scoped to the tenant (``team_id``) embedded in the
caller's JWT.  The ``X-Team-Id`` header is never read — this prevents
cross-tenant access even if a client attempts to forge it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user, require_admin
from app.models.member import Role
from app.schemas.common import PaginationParams
from app.schemas.member import (
    MemberCreate,
    MemberResponse,
    MemberUpdate,
    PaginatedMembers,
    SuccessResponse,
)
from app.services import member_service

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=PaginatedMembers)
async def list_members(
    pagination: Annotated[PaginationParams, Depends()],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    role: Annotated[Role | None, Query(description="按角色筛选")] = None,
    name: Annotated[str | None, Query(description="按姓名模糊搜索")] = None,
) -> PaginatedMembers:
    """Retrieve a paginated list of team members."""
    items, total = await member_service.list_members(
        db,
        team_id=current.team_id,
        pagination=pagination,
        role=role.value if role else None,
        name=name,
    )
    resp_items = [MemberResponse.model_validate(m) for m in items]
    return PaginatedMembers.create(resp_items, total, pagination.page, pagination.page_size)


@router.get("/{member_id}", response_model=MemberResponse)
async def get_member(
    member_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    """Retrieve a single member by ID."""
    member = await member_service.get_member(db, current.team_id, member_id)
    return MemberResponse.model_validate(member)


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def create_member(
    payload: MemberCreate,
    current: Annotated[CurrentUser, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    """Create a new team member (admin only)."""
    member = await member_service.create_member(
        db,
        team_id=current.team_id,
        name=payload.name,
        email=payload.email,
        password=payload.password,
        role=payload.role,
        github_username=payload.github_username,
    )
    return MemberResponse.model_validate(member)


@router.put("/{member_id}", response_model=MemberResponse)
async def update_member(
    member_id: str,
    payload: MemberUpdate,
    current: Annotated[CurrentUser, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    """Update a member's information (admin only)."""
    member = await member_service.update_member(
        db,
        team_id=current.team_id,
        member_id=member_id,
        name=payload.name,
        email=payload.email,
        role=payload.role,
        github_username=payload.github_username,
    )
    return MemberResponse.model_validate(member)


@router.delete("/{member_id}", response_model=SuccessResponse)
async def delete_member(
    member_id: str,
    current: Annotated[CurrentUser, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Delete a member (admin only)."""
    await member_service.delete_member(
        db,
        current.team_id,
        member_id,
        current_user_id=str(current.user.id),
    )
    return SuccessResponse(message="删除成功")
