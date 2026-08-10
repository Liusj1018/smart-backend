"""Refresh Token blacklist with rotation support.

Implements the Refresh Token rotation mechanism required by ADR-SEC-006:
- When a refresh token is used, it is immediately blacklisted.
- A new refresh token is issued, linked to the same "family" (chain).
- If a blacklisted token is ever presented again, the entire family is
  marked as compromised and all tokens in that chain are rejected.

Storage is in-memory (sufficient for single-instance deployments).
For multi-instance deployments, replace with Redis or a database table.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class _BlacklistEntry:
    """Tracks a used refresh token and its family."""

    family_id: str
    compromised: bool = False


@dataclass
class TokenBlacklist:
    """Thread-safe in-memory refresh token blacklist."""

    # jti -> entry (for individual token lookup)
    _tokens: dict[str, _BlacklistEntry] = field(default_factory=dict)
    # family_id -> set of jti (for bulk invalidation on replay)
    _families: dict[str, set[str]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def is_blacklisted(self, jti: str) -> bool:
        """Return True if this specific token has been used before."""
        with self._lock:
            return jti in self._tokens

    def is_family_compromised(self, family_id: str) -> bool:
        """Return True if this token family has been marked compromised."""
        with self._lock:
            for token_jti in self._families.get(family_id, set()):
                token_entry = self._tokens.get(token_jti)
                if token_entry and token_entry.compromised:
                    return True
            return False

    def revoke(self, jti: str, family_id: str) -> None:
        """Mark a refresh token as used (blacklist it).

        Also checks if the token was already blacklisted — if so, the
        entire family is marked as compromised (replay attack detected).
        """
        with self._lock:
            if jti in self._tokens:
                # Replay detected! Mark entire family as compromised.
                self._mark_family_compromised(family_id)
                return

            self._tokens[jti] = _BlacklistEntry(family_id=family_id)
            if family_id not in self._families:
                self._families[family_id] = set()
            self._families[family_id].add(jti)

    def _mark_family_compromised(self, family_id: str) -> None:
        """Mark all tokens in a family as compromised. Caller must hold lock."""
        for token_jti in self._families.get(family_id, set()):
            entry = self._tokens.get(token_jti)
            if entry:
                entry.compromised = True


# Singleton instance
token_blacklist = TokenBlacklist()
