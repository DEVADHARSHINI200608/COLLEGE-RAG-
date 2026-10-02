"""
Authentication routes — register, login, refresh, logout, me.
"""
from __future__ import annotations

from datetime import timedelta

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_handler import create_access_token, create_refresh_token, verify_refresh_token
from auth.dependencies import get_current_user
from database.connection import get_db
from database.models import User, UserRole
from security.audit import log_event
from config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Schemas ────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.STUDENT
    department: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    full_name: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    department: str | None
    is_active: bool


# ─── Helpers ────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    # bcrypt requires ≤72 bytes; truncate safely
    pw_bytes = password.encode("utf-8")[:72]
    return _bcrypt.hashpw(pw_bytes, _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pw_bytes = plain.encode("utf-8")[:72]
    return _bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))


# ─── Routes ─────────────────────────────────────────────────────────────
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Check existing email
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role.value,
        department=body.department,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    await log_event(db, "USER_REGISTERED", user_id=str(user.id),
                    ip_address=request.client.host if request.client else None)

    return UserResponse(
        id=str(user.id), email=user.email, full_name=user.full_name,
        role=user.role, department=user.department, is_active=user.is_active,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated.")

    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Set httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    await log_event(db, "USER_LOGIN", user_id=str(user.id),
                    ip_address=request.client.host if request.client else None)

    return TokenResponse(
        access_token=access_token,
        user_id=str(user.id),
        role=user.role,
        full_name=user.full_name,
    )


@router.post("/logout")
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        department=current_user.department,
        is_active=current_user.is_active,
    )
