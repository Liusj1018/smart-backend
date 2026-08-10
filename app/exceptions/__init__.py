"""Custom exception classes for the application."""


class AppError(Exception):
    """Base exception for application errors."""

    status_code: int = 500
    title: str = "Internal Server Error"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    title = "Not Found"


class ForbiddenError(AppError):
    """Raised when the caller lacks permission for the operation."""

    status_code = 403
    title = "Forbidden"


class ValidationError(AppError):
    """Raised when input validation fails beyond Pydantic checks."""

    status_code = 422
    title = "Validation Error"


class ConflictError(AppError):
    """Raised when a resource conflict occurs (e.g. duplicate email)."""

    status_code = 409
    title = "Conflict"


class UnauthorizedError(AppError):
    """Raised when authentication fails (invalid credentials or token)."""

    status_code = 401
    title = "Unauthorized"
