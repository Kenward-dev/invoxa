"""Application-specific exception types and HTTP conversion helpers."""

from fastapi import HTTPException, status


class AppError(Exception):
    """Base exception for expected application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "An unexpected error occurred."

    def __init__(self, detail: str | None = None) -> None:
        """Initialize the error with an optional custom detail message."""
        self.detail = detail or self.detail

    def to_http(self) -> HTTPException:
        """Convert the application error to a FastAPI HTTPException."""
        return HTTPException(
            status_code=self.status_code,
            detail=self.detail,
        )


class NotFoundError(AppError):
    """Raised when a requested resource cannot be found."""

    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found."


class ConflictError(AppError):
    """Raised when a request conflicts with existing state."""

    status_code = status.HTTP_409_CONFLICT
    detail = "Resource already exists."


class UnauthorizedError(AppError):
    """Raised when authentication fails or is missing."""

    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Invalid credentials."


class ForbiddenError(AppError):
    """Raised when an authenticated user lacks permission."""

    status_code = status.HTTP_403_FORBIDDEN
    detail = "Access denied."
