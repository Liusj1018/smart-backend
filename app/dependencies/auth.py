"""Authentication and authorization dependencies.

Every authenticated request resolves the caller from the JWT and
establishes the tenant context (``team_id``) from the token itself —
never from a client-supplied header.  This is the foundation of the
multi-tenant isolation guarantee (ADR-AUTH-001).
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.jwt_tokens import TOKEN_TYPE_ACCESS, decode_token
from app.db.models import User as UserRow
from app.db.session import get_db
from app.exceptions import ForbiddenError, UnauthorizedError

# auto_error=False so we can raise our own RFC 7807 response
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated principal resolved from the JWT.

    Attributes:
        user: The ``User`` ORM row (eagerly loaded with team memberships).
        team_id: The tenant UUID this token is scoped to — taken from the
            JWT, **not** from any request header.
        role: The user's role within ``team_id`` — taken from the JWT.
    """

    user: UserRow
    team_id: str
    role: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Decode and validate the Bearer JWT, returning the current user.

    The ``team_id`` and ``role`` claims embedded in the token establish
    the security context.  The ``X-Team-Id`` / ``X-User-Role`` headers
    are intentionally ignored — they cannot be trusted.

    Raises:
        UnauthorizedError: 401 when the token is missing, invalid,
            expired, or references a non-existent user / membership.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("请先登录")

    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("登录已过期，请重新登录") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("无效的认证凭证") from exc

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise UnauthorizedError("无效的认证凭证")

    user_id: str | None = payload.get("sub")
    team_id: str | None = payload.get("team_id")
    role: str | None = payload.get("role")

    if not user_id or not team_id or not role:
        raise UnauthorizedError("无效的认证凭证")

    # Load user with their memberships so role checks can be performed
    # without additional queries.
    result = await db.execute(
        select(UserRow)
        .where(UserRow.id == user_id)
        .options(selectinload(UserRow.team_memberships))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("无效的认证凭证")

    # Verify the user is actually a member of the team claimed in the token.
    membership = next(
        (m for m in user.team_memberships if str(m.team_id) == team_id),
        None,
    )
    if membership is None:
        raise UnauthorizedError("无效的认证凭证")

    return CurrentUser(user=user, team_id=team_id, role=role)


async def require_admin(
    current: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Require the caller to have the ``admin`` role in the current team.

    The role is taken from the JWT (set at login from the database) and
    cross-checked against the live membership row.

    Raises:
        ForbiddenError: 403 if the user is not an admin.
    """
    if current.role != "admin":
        raise ForbiddenError("需要管理员权限")
    return current
