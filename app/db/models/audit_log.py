"""AuditLog model — append-only audit trail for team-scoped actions."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.team import Team
    from app.db.models.user import User


class AuditLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only audit log. No updated_at — records are immutable."""

    __tablename__ = "audit_logs"

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    team: Mapped["Team"] = relationship(back_populates="audit_logs")
    user: Mapped["User"] = relationship(back_populates="audit_logs")
