"""Commit model — a git commit scoped to a team, user, and repo."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.repo import Repo
    from app.db.models.team import Team
    from app.db.models.user import User


class Commit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A git commit record linked to team, user, and repository."""

    __tablename__ = "commits"

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    repo_id: Mapped[UUID] = mapped_column(
        ForeignKey("repos.id"), nullable=False, index=True
    )
    sha: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    additions: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    deletions: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    ai_percentage: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    committed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Relationships
    team: Mapped["Team"] = relationship(back_populates="commits")
    user: Mapped["User"] = relationship(back_populates="commits")
    repo: Mapped["Repo"] = relationship(back_populates="commits")
