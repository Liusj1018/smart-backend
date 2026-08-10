"""Authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import CurrentUser, get_current_user
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
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
)
async def register(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RegisterResponse:
    """Register a new user account.

    - Email must be unique and valid.
    - Password must be at least 8 characters with uppercase, lowercase, and digit.
    - Returns the new user's id, email, and name (never the password hash).
    """
    return await auth_service.register_user(db, payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="用户登录",
)
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate a user and return JWT tokens.

    - Accepts email and password.
    - Returns access_token (15 min) and refresh_token (7 days).
    - On failure, returns 401 with a generic message (no email enumeration).
    """
    return await auth_service.login_user(db, payload)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="刷新 Access Token",
)
async def refresh(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Exchange a valid refresh token for a new access token.

    - Validates the refresh token signature and expiry.
    - Enforces one-time use via a blacklist (rotation).
    - Replay of an old token invalidates the entire token family.
    - Expired refresh token returns 401 with "请重新登录".
    """
    return await auth_service.refresh_token(db, payload)


@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
    summary="获取当前用户信息",
)
async def get_me(
    current: Annotated[CurrentUser, Depends(get_current_user)],
) -> MeResponse:
    """Return the profile of the currently authenticated user.

    - Requires a valid Bearer access token.
    - Returns id, email, name, team_id, and role.
    """
    return await auth_service.get_me(current)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="用户登出",
)
async def logout(
    payload: LogoutRequest | None = None,
) -> LogoutResponse:
    """Log out the current user.

    - If a refresh token is provided in the body, it is blacklisted.
    - The client should discard the access token (it expires in 15 min).
    - This endpoint is idempotent — it always succeeds.
    """
    body = payload or LogoutRequest()
    return await auth_service.logout(body)
