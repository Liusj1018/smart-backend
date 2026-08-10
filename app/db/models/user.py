"""User model — global user entity (cross-team)."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.audit_log import AuditLog
    from app.db.models.commit import Commit
    from app.db.models.repo_member import RepoMember
    from app.db.models.team_member import TeamMember


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user is a global entity that can belong to multiple teams."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_username: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    # Relationships
    team_memberships: Mapped[list["TeamMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    repo_memberships: Mapped[list["RepoMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    commits: Mapped[list["Commit"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
