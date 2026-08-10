"""RepoMember model — many-to-many association between Repo and User."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.repo import Repo
    from app.db.models.user import User


class RepoMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Association table linking users to repos with role metadata."""

    __tablename__ = "repo_members"
    __table_args__ = (
        UniqueConstraint("repo_id", "user_id", name="uq_repo_members_repo_id_user_id"),
    )

    repo_id: Mapped[UUID] = mapped_column(
        ForeignKey("repos.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="developer"
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    repo: Mapped["Repo"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="repo_memberships")
