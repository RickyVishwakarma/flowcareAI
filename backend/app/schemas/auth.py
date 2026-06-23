"""Auth-related schemas."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.models.base import UserRole


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class SignupRequest(BaseModel):
    organization_name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class MessageResponse(BaseModel):
    detail: str


class ResendVerificationResponse(MessageResponse):
    """In non-prod, includes the link so it can be used without an inbox."""

    verification_link: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
    role: UserRole = UserRole.AGENT


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None
    role: UserRole
    organization_id: str
    is_active: bool

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    """Current-user payload for the UI — includes the organization name."""

    id: str
    email: EmailStr
    full_name: str | None
    role: UserRole
    organization_id: str
    organization_name: str
    is_active: bool
    email_verified: bool


class VerifyEmailRequest(BaseModel):
    token: str


class SignupResponse(Token):
    """Tokens plus (in non-prod) the verification link, so the flow is testable."""

    verification_link: str | None = None
