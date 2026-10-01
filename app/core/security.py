"""
Authentication primitives: password hashing and JWT issuance/verification.

This is the Phase 1 "authentication foundation" — enough to register/login
users with ADMIN or TENANT roles and protect routes with role checks. Token
refresh, password reset flows, and rate limiting are out of scope for
Phase 1.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    role: str,
    tenant_id: Optional[int] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT access token.

    The token embeds `sub` (user id), `role` (ADMIN/TENANT), and `tenant_id`
    (present only for TENANT users) so that API routers can enforce
    role- and tenant-scoping without an extra database lookup on every
    request. Sensitive tenant-scoped endpoints still re-verify against the
    database in later phases once tenant-owned data tables exist.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "tenant_id": tenant_id,
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT. Raises `jose.JWTError` on invalid/expired
    tokens — callers are expected to translate that into an HTTP 401.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as exc:
        raise exc
