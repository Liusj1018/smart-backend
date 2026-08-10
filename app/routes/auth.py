"""Authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
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
