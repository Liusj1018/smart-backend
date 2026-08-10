"""JWT Token generation and verification.

Uses HS256 algorithm with secret from environment variable JWT_SECRET.
- Access Token: 15 minutes, payload contains sub, role, team_id, exp, type
- Refresh Token: 7 days, payload contains sub, exp, type, jti, fam

The ``jti`` (JWT ID) uniquely identifies each token and is used for
blacklisting.  The ``fam`` (family) groups tokens in a refresh chain
so that replay of an old token can invalidate the entire chain
(ADR-SEC-006).

Payload is minimal — never includes password or other sensitive data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import settings

# Token type constants
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def create_access_token(
    user_id: str,
    role: str,
    team_id: str,
    expires_minutes: int | None = None,
) -> str:
    """Create a short-lived access token.

    Args:
        user_id: The user's UUID as a string.
        role: The user's role within the team (e.g. "admin", "developer").
        team_id: The team UUID this token is scoped to.
        expires_minutes: Override token lifetime in minutes.  Defaults to
            ``settings.access_token_expire_minutes``.  Primarily useful
            in tests for creating already-expired tokens.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    minutes = expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "team_id": team_id,
        "type": TOKEN_TYPE_ACCESS,
        "exp": now + timedelta(minutes=minutes),
        "iat": now,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, family_id: str | None = None) -> tuple[str, str, str]:
    """Create a long-lived refresh token.

    Args:
        user_id: The user's UUID as a string.
        family_id: Existing family ID for token rotation.  When ``None``
            a new family is started (initial login).

    Returns:
        A tuple of ``(encoded_token, jti, family_id)``.
    """
    now = datetime.now(UTC)
    jti = uuid.uuid4().hex
    fam = family_id or uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": TOKEN_TYPE_REFRESH,
        "jti": jti,
        "fam": fam,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
        "iat": now,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, fam


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT token.

    Validates signature and expiration time.

    Args:
        token: The encoded JWT string.

    Returns:
        Decoded payload dictionary.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is invalid (bad signature, etc.).
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
