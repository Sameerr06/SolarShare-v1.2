"""
Shared FastAPI dependencies: current-user extraction and role enforcement.

`require_role(...)` is the mechanism later phases will use to gate
admin-only endpoints (estate config, tariff config, tenant management,
triggering ingestion/forecasting/allocation/billing runs) versus
tenant-scoped read endpoints.
"""

from typing import Iterable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise credentials_exception

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise credentials_exception

    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        raise credentials_exception

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            return None
        user = db.get(User, int(user_id_raw))
        if user is not None and user.is_active:
            return user
    except Exception:
        pass
    return None


def verify_tenant_access(target_tenant_id: int, current_user: Optional[User]) -> None:
    """
    Enforces tenant isolation.
    If the user is logged in with TENANT role, they can ONLY access their own tenant_id.
    """
    if current_user and current_user.role == UserRole.TENANT:
        if current_user.tenant_id != target_tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Tenant {current_user.tenant_id} is not authorized to access tenant {target_tenant_id} data.",
            )


def require_role(*allowed_roles: Iterable[UserRole]):
    """
    Dependency factory: `Depends(require_role(UserRole.ADMIN))` restricts a
    route to the given role(s). Raises 403 for authenticated-but-unauthorized
    users, keeping it distinct from the 401 raised for unauthenticated
    requests.
    """
    allowed = set(allowed_roles)

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' is not permitted to access this resource.",
            )
        return current_user

    return _check

