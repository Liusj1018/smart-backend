"""Authentication request/response schemas."""

from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Email regex: standard email format
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Password: at least 8 chars, 1 uppercase, 1 lowercase, 1 digit
_PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: Annotated[
        str,
        Field(
            min_length=3,
            max_length=255,
            description="User email address",
            examples=["user@example.com"],
        ),
    ]
    password: Annotated[
        str,
        Field(
            min_length=8,
            max_length=128,
            description="Password (min 8 chars, must include uppercase, lowercase, digit)",
        ),
    ]
    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description="Display name",
            examples=["Alice Zhang"],
        ),
    ]
    team_id: Annotated[
        UUID,
        Field(description="Team to join"),
    ]

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Validate email format using regex."""
        if not _EMAIL_RE.match(v):
            raise ValueError("邮箱格式不正确")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets strength requirements."""
        if not _PASSWORD_RE.match(v):
            raise ValueError("密码至少8位，必须包含大写字母、小写字母和数字")
        return v


class RegisterResponse(BaseModel):
    """Response after successful registration."""

    id: Annotated[str, Field(description="User UUID")]
    email: Annotated[str, Field(description="User email")]
    name: Annotated[str, Field(description="Display name")]


class LoginRequest(BaseModel):
    """Request body for user login."""

    email: Annotated[
        str,
        Field(
            min_length=3,
            max_length=255,
            description="User email address",
            examples=["user@example.com"],
        ),
    ]
    password: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            description="User password",
        ),
    ]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase for case-insensitive login."""
        return v.lower()


class TokenResponse(BaseModel):
    """Response after successful login containing JWT tokens."""

    access_token: Annotated[str, Field(description="Short-lived JWT access token")]
    refresh_token: Annotated[str, Field(description="Long-lived JWT refresh token")]
    token_type: Annotated[str, Field(default="bearer", description="Token type")]
    expires_in: Annotated[
        int,
        Field(description="Access token expiry in seconds", ge=1),
    ]


class RefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: Annotated[
        str,
        Field(min_length=1, description="A valid refresh token"),
    ]


class MeResponse(BaseModel):
    """Response containing the current authenticated user's information."""

    id: Annotated[str, Field(description="User UUID")]
    email: Annotated[str, Field(description="User email")]
    name: Annotated[str, Field(description="Display name")]
    team_id: Annotated[str, Field(description="Current team UUID")]
    role: Annotated[str, Field(description="User role within the team")]


class LogoutRequest(BaseModel):
    """Optional request body for logout.

    The refresh token is optional — when provided, it is blacklisted
    immediately so it cannot be reused.
    """

    refresh_token: Annotated[
        str | None,
        Field(default=None, description="Refresh token to revoke"),
    ] = None


class LogoutResponse(BaseModel):
    """Response after successful logout."""

    message: Annotated[str, Field(default="退出成功")]
