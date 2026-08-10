"""Role-based access control dependencies."""

from __future__ import annotations

from fastapi import Depends

from app.db.models import User as UserRow
from app.dependencies.auth import get_current_user
from app.exceptions import ForbiddenError


async def require_admin(
    current_user: UserRow = Depends(get_current_user),
) -> UserRow:
    """Require the current user to have an admin role in at least one team.

    Returns:
        The authenticated ``User`` if they are an admin.

    Raises:
        ForbiddenError: 403 if the user is not an admin in any team.
    """
    roles = {m.role for m in current_user.team_memberships}
    if "admin" not in roles:
        raise ForbiddenError("需要管理员权限")
    return current_user
