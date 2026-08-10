"""Team model — root tenant entity."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.audit_log import AuditLog
    from app.db.models.commit import Commit
    from app.db.models.repo import Repo
    from app.db.models.team_member import TeamMember


class Team(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A team is the top-level tenant. All other data is scoped to a team."""

    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    # Relationships
    members: Mapped[list["TeamMember"]] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
    )
    repos: Mapped[list["Repo"]] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
    )
    commits: Mapped[list["Commit"]] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
    )
