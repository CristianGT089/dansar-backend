from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class UserCompanyInfo(BaseModel):
    id: str
    name: str
    role: str
    features: list[str]


class MeResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_superadmin: bool
    companies: list[UserCompanyInfo]
