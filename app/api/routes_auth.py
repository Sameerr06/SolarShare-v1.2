"""
Authentication endpoints: register, login (OAuth2 password flow), and the
current-user endpoint.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import Token, UserRead, UserRegister

from sqlalchemy import func

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> UserRead:
    existing = db.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username or email already registered")

    tenant_name = None
    series_id = None
    if payload.tenant_id is not None:
        tenant = db.get(Tenant, payload.tenant_id)
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_id does not exist")
        tenant_name = tenant.name
        series_id = tenant.source_client_series_id

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        tenant_id=payload.tenant_id,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username or email already registered")
    db.refresh(user)

    logger.info("Registered new user id=%s role=%s", user.id, user.role.value)
    return UserRead(
        id=user.id,
        email=user.email,
        role=user.role,
        tenant_id=user.tenant_id,
        tenant_name=tenant_name,
        source_client_series_id=series_id,
        is_active=user.is_active,
    )


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    username_input = form_data.username.strip()
    user = db.query(User).filter(
        (func.lower(User.email) == username_input.lower()) |
        (func.lower(User.email) == f"{username_input.lower()}@solarshare.com")
    ).first()

    if user is None:
        tenant = db.query(Tenant).filter(func.lower(Tenant.source_client_series_id) == username_input.lower()).first()
        if tenant is not None:
            user = db.query(User).filter(User.tenant_id == tenant.id).first()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    access_token = create_access_token(subject=user.id, role=user.role.value, tenant_id=user.tenant_id)
    logger.info("User id=%s logged in", user.id)
    return Token(access_token=access_token)


@router.get("/me", response_model=UserRead)
def read_current_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRead:
    tenant_name = None
    series_id = None
    if current_user.tenant_id is not None:
        tenant = db.get(Tenant, current_user.tenant_id)
        if tenant is not None:
            tenant_name = tenant.name
            series_id = tenant.source_client_series_id

    return UserRead(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        tenant_name=tenant_name,
        source_client_series_id=series_id,
        is_active=current_user.is_active,
    )

