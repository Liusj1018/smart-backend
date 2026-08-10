"""Re-export common dependencies for convenience."""

from app.dependencies.auth import CurrentUser, get_current_user, require_admin

__all__ = ["CurrentUser", "get_current_user", "require_admin"]
