"""Pydantic schemas for authentication and user endpoints."""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.enums import UserRole


class UserRegister(BaseModel):
    email: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)
    role: UserRole
    tenant_id: Optional[int] = None

    @model_validator(mode="after")
    def tenant_role_consistency(self) -> "UserRegister":
        if self.role == UserRole.TENANT and self.tenant_id is None:
            raise ValueError("tenant_id is required when role is TENANT")
        if self.role == UserRole.ADMIN and self.tenant_id is not None:
            raise ValueError("tenant_id must not be set when role is ADMIN")
        return self


class UserLogin(BaseModel):
    username: str
    password: str


class UserRead(BaseModel):
    id: int
    email: str
    role: UserRole
    tenant_id: Optional[int] = None
    tenant_name: Optional[str] = None
    source_client_series_id: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: UserRole
    tenant_id: Optional[int] = None

