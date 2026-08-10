"""Request/response schemas for Commit and Workload endpoints."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.common import PageResponse


class CommitResponse(BaseModel):
    """Response schema for a single commit."""

    id: str
    member_id: str
    sha: str
    message: str
    repository: str
    branch: str
    lines_added: int
    lines_deleted: int
    ai_percentage: int
    committed_at: datetime


class CommitDetailResponse(BaseModel):
    """Response schema for commit detail (includes team_id)."""

    id: str
    team_id: str
    member_id: str
    sha: str
    message: str
    repository: str
    branch: str
    lines_added: int
    lines_deleted: int
    ai_percentage: int
    committed_at: datetime


class CommitListResponse(PageResponse[CommitResponse]):
    """Paginated list of commits."""


class WorkloadResponse(BaseModel):
    """Response schema for member workload statistics."""

    member_id: str
    user_id: str
    total_commits: Annotated[int, Field(ge=0)]
    total_lines_added: Annotated[int, Field(ge=0)]
    total_lines_deleted: Annotated[int, Field(ge=0)]
    period_start: datetime | None = None
    period_end: datetime | None = None
