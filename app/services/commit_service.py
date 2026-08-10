"""Business logic for commit queries and workload statistics."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.db.models import Commit as CommitRow
from app.db.models import Repo as RepoRow
from app.db.models import TeamMember as TeamMemberRow
from app.exceptions import NotFoundError, ValidationError
from app.models.commit import Workload as WorkloadSummary
from app.schemas.commit import CommitDetailResponse, CommitResponse
from app.schemas.common import PaginationParams


def _parse_uuid(value: str, field: str) -> UUID:
    """Parse a string as UUID, raising NotFoundError on failure."""
    try:
        return UUID(value)
    except (ValueError, AttributeError) as exc:
        raise NotFoundError(f"{field} {value} not found") from exc


def _to_response(row: CommitRow, tm_id: UUID) -> CommitResponse:
    """Map a Commit ORM row (with eager-loaded repo) to a CommitResponse."""
    return CommitResponse(
        id=str(row.id),
        member_id=str(tm_id),
        sha=row.sha,
        message=row.message,
        repository=row.repo.name if row.repo else "",
        branch="main",
        lines_added=row.additions,
        lines_deleted=row.deletions,
        ai_percentage=row.ai_percentage,
        committed_at=row.committed_at,
    )


def _to_detail_response(row: CommitRow, tm_id: UUID) -> CommitDetailResponse:
    """Map a Commit ORM row to a CommitDetailResponse."""
    return CommitDetailResponse(
        id=str(row.id),
        team_id=str(row.team_id),
        member_id=str(tm_id),
        sha=row.sha,
        message=row.message,
        repository=row.repo.name if row.repo else "",
        branch="main",
        lines_added=row.additions,
        lines_deleted=row.deletions,
        ai_percentage=row.ai_percentage,
        committed_at=row.committed_at,
    )


async def list_commits(
    db: AsyncSession,
    team_id: str,
    pagination: PaginationParams,
    *,
    member_id: str | None = None,
    repository: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> tuple[list[CommitResponse], int]:
    """Return paginated commits for the given team with optional filters.

    Uses JOIN repos for repository name filtering and SELECT DISTINCT for
    correct pagination when joining repo_members.
    """
    if start_date and end_date and start_date > end_date:
        raise ValidationError("start_date must be before end_date")

    # Count query with JOIN repos for repository name filtering
    count_stmt = (
        select(func.count(func.distinct(CommitRow.id)))
        .select_from(CommitRow)
        .join(RepoRow, CommitRow.repo_id == RepoRow.id)
        .where(CommitRow.team_id == team_id)
    )

    # Data query with JOIN repos and team_members to get TeamMember.id
    stmt = (
        select(CommitRow, TeamMemberRow.id.label("tm_id"))
        .join(RepoRow, CommitRow.repo_id == RepoRow.id)
        .join(
            TeamMemberRow,
            (TeamMemberRow.user_id == CommitRow.user_id)
            & (TeamMemberRow.team_id == CommitRow.team_id),
        )
        .options(contains_eager(CommitRow.repo))
        .where(CommitRow.team_id == team_id)
        .order_by(CommitRow.committed_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )

    if member_id:
        # Resolve TeamMember.id -> User.id
        member_uuid = _parse_uuid(member_id, "member_id")
        subq = select(TeamMemberRow.user_id).where(
            TeamMemberRow.id == member_uuid,
            TeamMemberRow.team_id == team_id,
        )
        count_stmt = count_stmt.where(CommitRow.user_id.in_(subq))
        stmt = stmt.where(CommitRow.user_id.in_(subq))
    if repository:
        count_stmt = count_stmt.where(RepoRow.name == repository)
        stmt = stmt.where(RepoRow.name == repository)
    if start_date:
        count_stmt = count_stmt.where(CommitRow.committed_at >= start_date)
        stmt = stmt.where(CommitRow.committed_at >= start_date)
    if end_date:
        count_stmt = count_stmt.where(CommitRow.committed_at <= end_date)
        stmt = stmt.where(CommitRow.committed_at <= end_date)

    total = (await db.execute(count_stmt)).scalar_one()
    result = (await db.execute(stmt)).all()

    return [_to_response(r[0], r[1]) for r in result], total


async def get_commit(
    db: AsyncSession,
    team_id: str,
    commit_id: str,
) -> CommitDetailResponse:
    """Fetch a single commit by ID, scoped to the given team."""
    commit_uuid = _parse_uuid(commit_id, "commit_id")
    stmt = (
        select(CommitRow, TeamMemberRow.id.label("tm_id"))
        .join(RepoRow, CommitRow.repo_id == RepoRow.id)
        .join(
            TeamMemberRow,
            (TeamMemberRow.user_id == CommitRow.user_id)
            & (TeamMemberRow.team_id == CommitRow.team_id),
        )
        .options(contains_eager(CommitRow.repo))
        .where(CommitRow.id == commit_uuid, CommitRow.team_id == team_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise NotFoundError(f"Commit {commit_id} not found")
    return _to_detail_response(row[0], row[1])


async def get_workload(
    db: AsyncSession,
    team_id: str,
    member_id: str,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> WorkloadSummary:
    """Aggregate commit statistics for a team member.

    Uses SELECT ... FOR SHARE to lock team_members row and prevent
    concurrent role changes during aggregation.
    """
    if start_date and end_date and start_date > end_date:
        raise ValidationError("start_date must be before end_date")

    # Resolve TeamMember.id -> row, lock for share
    member_uuid = _parse_uuid(member_id, "member_id")
    member_stmt = (
        select(TeamMemberRow)
        .where(
            TeamMemberRow.team_id == team_id,
            TeamMemberRow.id == member_uuid,
        )
        .with_for_update(read=True)
    )
    member = (await db.execute(member_stmt)).scalar_one_or_none()
    if member is None:
        raise NotFoundError(f"Member {member_id} not found in team")
    user_id = member.user_id

    # Build aggregate query
    agg_stmt = select(
        func.count(CommitRow.id).label("total_commits"),
        func.coalesce(func.sum(CommitRow.additions), 0).label("total_additions"),
        func.coalesce(func.sum(CommitRow.deletions), 0).label("total_deletions"),
        func.min(CommitRow.committed_at).label("period_start"),
        func.max(CommitRow.committed_at).label("period_end"),
    ).where(
        CommitRow.team_id == team_id,
        CommitRow.user_id == user_id,
    )

    if start_date:
        agg_stmt = agg_stmt.where(CommitRow.committed_at >= start_date)
    if end_date:
        agg_stmt = agg_stmt.where(CommitRow.committed_at <= end_date)

    result = (await db.execute(agg_stmt)).one()

    return WorkloadSummary(
        member_id=str(member.id),
        user_id=str(user_id),
        team_id=team_id,
        total_commits=result.total_commits,
        total_lines_added=result.total_additions,
        total_lines_deleted=result.total_deletions,
        period_start=result.period_start,
        period_end=result.period_end,
    )
