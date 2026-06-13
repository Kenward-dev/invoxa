"""Password hashing and JWT helpers for authentication flows."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(password: str) -> str:
    """Return a bcrypt hash for a plaintext password."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a stored password hash."""
    return pwd_context.verify(plain, hashed)


def _create_token(
    subject: str,
    token_type: str,
    extra_claims: dict[str, Any],
    expires_delta: timedelta,
) -> str:
    """Create a signed JWT with shared claims and a caller-provided expiry."""
    now = datetime.now(UTC)

    payload = {
        "sub": subject,
        "type": token_type,
        "jti": str(uuid4()),
        "exp": now + expires_delta,
        "iat": now,
        **extra_claims,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_access_token(user_id: str, tenant_id: str, role: str) -> str:
    """Create a short-lived access token for an authenticated user."""
    return _create_token(
        subject=user_id,
        token_type="access",
        extra_claims={"tenant_id": tenant_id, "role": role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived refresh token for an authenticated user."""
    return _create_token(
        subject=user_id,
        token_type="refresh",
        extra_claims={},
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, raising ValueError for invalid tokens."""
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError as e:
        raise ValueError("Invalid token") from e


def verify_token_type(payload: dict[str, Any], expected_type: str) -> bool:
    """Return whether a decoded JWT payload matches the expected token type."""
    return payload.get("type") == expected_type
