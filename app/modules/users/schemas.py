import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    is_superadmin: bool = False

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_superadmin: bool

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int


class AssignUserToCompanyRequest(BaseModel):
    user_id: uuid.UUID
    role: str = "viewer"

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        allowed = {"admin", "contador", "viewer"}
        if v not in allowed:
            raise ValueError(f"Rol inválido. Opciones: {allowed}")
        return v


class UserCompanyRoleResponse(BaseModel):
    user_id: uuid.UUID
    company_id: uuid.UUID
    role: str
    is_active: bool
    user: UserResponse

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v
