"""Repo model — code repository belonging to a team."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.commit import Commit
    from app.db.models.repo_member import RepoMember
    from app.db.models.team import Team


class Repo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A code repository owned by a team."""

    __tablename__ = "repos"

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    team: Mapped["Team"] = relationship(back_populates="repos")
    members: Mapped[list["RepoMember"]] = relationship(
        back_populates="repo",
        cascade="all, delete-orphan",
    )
    commits: Mapped[list["Commit"]] = relationship(
        back_populates="repo",
        cascade="all, delete-orphan",
    )
