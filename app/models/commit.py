"""Domain models for Commit and Workload."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class Commit(BaseModel):
    """Domain model representing a code commit."""

    id: Annotated[str, Field(description="Unique commit identifier")]
    team_id: Annotated[str, Field(description="Owning team identifier")]
    member_id: Annotated[str, Field(description="Author member identifier")]
    sha: Annotated[str, Field(min_length=7, max_length=64, description="Git commit SHA")]
    message: Annotated[str, Field(min_length=1, max_length=500, description="Commit message")]
    repository: Annotated[str, Field(min_length=1, max_length=200, description="Repository name")]
    branch: Annotated[str, Field(min_length=1, max_length=200, description="Branch name")]
    lines_added: Annotated[int, Field(ge=0, description="Lines added")]
    lines_deleted: Annotated[int, Field(ge=0, description="Lines deleted")]
    ai_percentage: Annotated[int, Field(ge=0, le=100, description="AI-generated code percentage (0-100)")] = 0
    committed_at: Annotated[datetime, Field(description="Commit timestamp")]


class Workload(BaseModel):
    """Domain model representing a member's workload statistics."""

    member_id: Annotated[str, Field(description="Member identifier")]
    user_id: Annotated[str, Field(description="User identifier")]
    team_id: Annotated[str, Field(description="Team identifier")]
    total_commits: Annotated[int, Field(ge=0, description="Total number of commits")]
    total_lines_added: Annotated[int, Field(ge=0, description="Total lines added")]
    total_lines_deleted: Annotated[int, Field(ge=0, description="Total lines deleted")]
    period_start: Annotated[datetime | None, Field(default=None, description="Stats period start")]
    period_end: Annotated[datetime | None, Field(default=None, description="Stats period end")]
