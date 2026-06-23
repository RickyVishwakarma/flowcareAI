"""Authentication: signup, login, refresh rotation, logout, password change.

Security features:
  * bcrypt password hashing
  * short-lived access tokens + rotating refresh tokens (server-side sessions)
  * refresh-token reuse detection (revokes the whole session family)
  * brute-force lockout (5 failures → 15 min lock)
  * logout / logout-all / change-password (revokes sessions)
  * RBAC-gated user provisioning
"""
from __future__ import annotations

import re

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.security import (
    RESET,
    VERIFY,
    create_email_token,
    create_reset_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.base import UserRole
from app.models.organization import Organization, User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutRequest,
    MeResponse,
    MessageResponse,
    RefreshRequest,
    ResendVerificationResponse,
    ResetPasswordRequest,
    SignupRequest,
    SignupResponse,
    Token,
    UserCreate,
    UserOut,
    VerifyEmailRequest,
)
from app.services import auth_service, email_service
from app.services.auth_service import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


def _meta(request: Request) -> dict:
    return {
        "user_agent": request.headers.get("user-agent"),
        "ip": request.client.host if request.client else None,
    }


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"
    return base[:48]


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, request: Request, db: Session = Depends(get_db)) -> SignupResponse:
    """Self-service: create an organization + its first admin, send a verification
    email, and log in."""
    if db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    slug = _slugify(payload.organization_name)
    n = 1
    while db.execute(select(Organization).where(Organization.slug == slug)).scalar_one_or_none():
        n += 1
        slug = f"{_slugify(payload.organization_name)}-{n}"

    org = Organization(name=payload.organization_name, slug=slug)
    db.add(org)
    db.flush()
    user = User(
        organization_id=org.id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=UserRole.ADMIN,
        email_verified=False,
    )
    db.add(user)
    db.flush()

    token = create_email_token(user.id)
    link = email_service.send_verification_email(user.email, token)

    access, refresh = auth_service.issue_fresh_session(db, user, _meta(request))
    return SignupResponse(
        access_token=access,
        refresh_token=refresh,
        verification_link=link if email_service.expose_link_in_response() else None,
    )


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> MessageResponse:
    try:
        decoded = decode_token(payload.token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired link") from exc
    if decoded.get("type") != VERIFY:
        raise HTTPException(status_code=400, detail="Not a verification token")
    user = db.get(User, decoded.get("sub"))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.email_verified:
        user.email_verified = True
        db.commit()
    return MessageResponse(detail="Email verified")


@router.post("/resend-verification", response_model=ResendVerificationResponse)
def resend_verification(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ResendVerificationResponse:
    if user.email_verified:
        return ResendVerificationResponse(detail="Email already verified")
    token = create_email_token(user.id)
    link = email_service.send_verification_email(user.email, token)
    return ResendVerificationResponse(
        detail="Verification email sent",
        verification_link=link if email_service.expose_link_in_response() else None,
    )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> ForgotPasswordResponse:
    """Request a password-reset link. Always returns 200 (no user enumeration)."""
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    link = None
    if user and user.is_active:
        token = create_reset_token(user.id)
        sent = email_service.send_password_reset_email(user.email, token)
        if email_service.expose_link_in_response():
            link = sent
    return ForgotPasswordResponse(
        detail="If an account exists for that email, a reset link has been sent.",
        reset_link=link,
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest, db: Session = Depends(get_db)
) -> MessageResponse:
    try:
        decoded = decode_token(payload.token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link") from exc
    if decoded.get("type") != RESET:
        raise HTTPException(status_code=400, detail="Not a password-reset token")
    user = db.get(User, decoded.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid reset link")

    user.hashed_password = hash_password(payload.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.flush()
    # Invalidate every existing session — a reset implies the account may be compromised.
    auth_service.revoke_all_for_user(db, user.id)
    db.commit()
    return MessageResponse(detail="Password reset. You can now sign in.")


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> Token:
    try:
        _, access, refresh = auth_service.authenticate(
            db, payload.email, payload.password, _meta(request)
        )
    except AuthError as exc:
        code = status.HTTP_423_LOCKED if exc.locked else status.HTTP_401_UNAUTHORIZED
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return Token(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> Token:
    try:
        access, refresh_token = auth_service.rotate(db, payload.refresh_token, _meta(request))
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return Token(access_token=access, refresh_token=refresh_token)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> MessageResponse:
    auth_service.revoke_by_token(db, payload.refresh_token)
    return MessageResponse(detail="Logged out")


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> MessageResponse:
    count = auth_service.revoke_all_for_user(db, user.id)
    return MessageResponse(detail=f"Revoked {count} session(s)")


@router.post("/change-password", response_model=Token)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Token:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    db.flush()
    # Invalidate every existing session, then start a fresh one for this client.
    auth_service.revoke_all_for_user(db, user.id)
    access, refresh = auth_service.issue_fresh_session(db, user, _meta(request))
    return Token(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
) -> User:
    """Admin/manager provisions a user inside their own organization."""
    if db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        organization_id=admin.organization_id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=MeResponse)
def me(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> MeResponse:
    org = db.get(Organization, user.organization_id)
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        organization_id=user.organization_id,
        organization_name=org.name if org else "",
        is_active=user.is_active,
        email_verified=user.email_verified,
    )
