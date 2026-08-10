"""Commit query endpoints.

All endpoints are scoped to the tenant (``team_id``) embedded in the
caller's JWT — never from a client-supplied header.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.commit import (
    CommitDetailResponse,
    CommitResponse,
    WorkloadResponse,
)
from app.schemas.common import PageResponse, PaginationParams
from app.services import commit_service

router = APIRouter(
    prefix="/commits",
    tags=["commits"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=PageResponse[CommitResponse], summary="提交列表")
async def list_commits(
    pagination: Annotated[PaginationParams, Depends()],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    member_id: Annotated[str | None, Query(description="按成员筛选")] = None,
    repository: Annotated[str | None, Query(description="按仓库筛选")] = None,
    start_date: Annotated[datetime | None, Query(description="起始日期")] = None,
    end_date: Annotated[datetime | None, Query(description="结束日期")] = None,
) -> PageResponse[CommitResponse]:
    """获取提交记录列表，支持分页和筛选。"""
    items, total = await commit_service.list_commits(
        db,
        current.team_id,
        pagination,
        member_id=member_id,
        repository=repository,
        start_date=start_date,
        end_date=end_date,
    )
    return PageResponse[CommitResponse].make(
        [CommitResponse.model_validate(item, from_attributes=True) for item in items],
        total,
        pagination,
    )


@router.get(
    "/{commit_id}",
    response_model=CommitDetailResponse,
    summary="提交详情",
)
async def get_commit(
    commit_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> CommitDetailResponse:
    """获取单条提交记录详情。"""
    return await commit_service.get_commit(db, current.team_id, commit_id)


@router.get(
    "/workload/{member_id}",
    response_model=WorkloadResponse,
    summary="成员工作量统计",
)
async def get_workload(
    member_id: str,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    start_date: Annotated[datetime | None, Query(description="起始日期")] = None,
    end_date: Annotated[datetime | None, Query(description="结束日期")] = None,
) -> WorkloadResponse:
    """获取指定成员的工作量统计。"""
    workload = await commit_service.get_workload(
        db, current.team_id, member_id, start_date=start_date, end_date=end_date
    )
    return WorkloadResponse(
        member_id=workload.member_id,
        user_id=workload.user_id,
        total_commits=workload.total_commits,
        total_lines_added=workload.total_lines_added,
        total_lines_deleted=workload.total_lines_deleted,
        period_start=workload.period_start,
        period_end=workload.period_end,
    )
