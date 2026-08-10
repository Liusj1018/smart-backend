"""Business logic for user authentication."""

from __future__ import annotations

import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.jwt_tokens import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.security import hash_password, verify_password
from app.db.models import TeamMember as TeamMemberRow
from app.db.models import User as UserRow
from app.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.middleware.token_blacklist import token_blacklist
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)


async def register_user(db: AsyncSession, body: RegisterRequest) -> RegisterResponse:
    """Register a new user.

    Validates that the email is not already registered, hashes the password,
    and creates both the User record and the TeamMember association.

    To prevent email enumeration, duplicate emails return a generic message
    that does not reveal whether the email is already in use.
    """
    normalized = body.email.lower()

    # Verify team exists
    from app.db.models import Team as TeamRow

    team = await db.get(TeamRow, body.team_id)
    if team is None:
        raise NotFoundError("团队不存在")

    # Check duplicate email (case-insensitive)
    result = await db.execute(select(UserRow).where(func.lower(UserRow.email) == normalized))
    if result.scalar_one_or_none() is not None:
        raise ConflictError("注册失败，请检查输入")

    user = UserRow(
        email=normalized,
        password_hash=hash_password(body.password),
        name=body.name,
    )
    db.add(user)
    await db.flush()

    # Create team membership
    membership = TeamMemberRow(
        team_id=body.team_id,
        user_id=user.id,
        role="member",
    )
    db.add(membership)
    await db.commit()
    await db.refresh(user)

    return RegisterResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
    )


async def login_user(db: AsyncSession, body: LoginRequest) -> TokenResponse:
    """Authenticate a user and issue JWT tokens.

    Verifies email and password against the database. On failure, returns
    a generic 401 error to prevent email enumeration.

    Args:
        db: Database session.
        body: Login credentials.

    Returns:
        TokenResponse with access and refresh tokens.

    Raises:
        UnauthorizedError: If email or password is incorrect.
    """
    normalized = body.email.lower()

    # Look up user by email
    result = await db.execute(select(UserRow).where(func.lower(UserRow.email) == normalized))
    user = result.scalar_one_or_none()

    # Generic error message to prevent email enumeration
    if user is None or not verify_password(body.password, user.password_hash):
        raise UnauthorizedError("用户名或密码错误")

    # Determine user's team and role from their first membership.
    # The token is scoped to a single team (multi-tenant isolation).
    membership_result = await db.execute(
        select(TeamMemberRow).where(TeamMemberRow.user_id == user.id).limit(1)
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        raise UnauthorizedError("用户名或密码错误")
    team_id = str(membership.team_id)
    role = membership.role

    access_token = create_access_token(str(user.id), role, team_id)
    refresh_token, _jti, _fam = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def refresh_token(db: AsyncSession, body: RefreshRequest) -> TokenResponse:
    """Exchange a valid refresh token for a new access token.

    Implements refresh-token rotation (ADR-SEC-006):
    1. Decode and verify the refresh token (signature + expiry).
    2. Verify the token type is ``refresh``.
    3. Check the token has not been blacklisted (already used).
    4. Check the token family has not been compromised (replay detected).
    5. Issue a new access token and a new refresh token in the same family.
    6. Blacklist the old refresh token.

    Args:
        db: Database session.
        body: Refresh request containing the refresh token.

    Returns:
        TokenResponse with a new access token and rotated refresh token.

    Raises:
        UnauthorizedError: If the token is expired, invalid, blacklisted,
            or the family has been compromised.
    """
    # Decode and verify signature + expiry
    try:
        payload = decode_token(body.refresh_token)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("请重新登录") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("无效的认证凭证") from exc

    # Verify token type
    if payload.get("type") != TOKEN_TYPE_REFRESH:
        raise UnauthorizedError("无效的认证凭证")

    jti: str | None = payload.get("jti")
    family_id: str | None = payload.get("fam")
    user_id: str | None = payload.get("sub")

    if not jti or not family_id or not user_id:
        raise UnauthorizedError("无效的认证凭证")

    # Check if family has been compromised (replay attack detected earlier)
    if token_blacklist.is_family_compromised(family_id):
        raise UnauthorizedError("检测到异常登录，请重新登录")

    # Check if this specific token has already been used
    if token_blacklist.is_blacklisted(jti):
        # Replay! Mark entire family as compromised
        token_blacklist.revoke(jti, family_id)
        raise UnauthorizedError("检测到异常登录，请重新登录")

    # Verify user still exists
    user = await db.get(UserRow, user_id)
    if user is None:
        raise UnauthorizedError("无效的认证凭证")

    # Determine team and role from the user's first membership
    membership_result = await db.execute(
        select(TeamMemberRow).where(TeamMemberRow.user_id == user.id).limit(1)
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        raise UnauthorizedError("无效的认证凭证")
    team_id = str(membership.team_id)
    role = membership.role

    # Issue new tokens — refresh token stays in the same family
    new_access = create_access_token(str(user.id), role, team_id)
    new_refresh, _new_jti, _new_fam = create_refresh_token(str(user.id), family_id)

    # Blacklist the old refresh token
    token_blacklist.revoke(jti, family_id)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def get_me(current_user) -> MeResponse:
    """Return the current authenticated user's profile.

    The user identity and tenant context come from the verified JWT
    via the ``get_current_user`` dependency — no database query needed
    because the user row was already loaded during authentication.
    """
    return MeResponse(
        id=str(current_user.user.id),
        email=current_user.user.email,
        name=current_user.user.name,
        team_id=current_user.team_id,
        role=current_user.role,
    )


async def logout(body: LogoutRequest) -> LogoutResponse:
    """Log the user out by revoking the refresh token.

    If a refresh token is provided in the request body, it is decoded
    and its ``jti`` is added to the blacklist so it cannot be reused.
    Invalid or expired tokens are silently ignored — logout is
    idempotent and always succeeds.

    Note: Access tokens are stateless JWTs and cannot be revoked
    before their natural expiry (15 minutes).  The client must
    discard them.
    """
    if body.refresh_token:
        try:
            payload = decode_token(body.refresh_token)
            jti = payload.get("jti")
            family_id = payload.get("fam")
            if jti and family_id:
                token_blacklist.revoke(jti, family_id)
        except jwt.InvalidTokenError:
            # Token is already invalid/expired — nothing to revoke
            pass

    return LogoutResponse(message="退出成功")
