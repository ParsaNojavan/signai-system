from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.dependencies import get_current_user, get_user_service
from server.schemas.user import User
from server.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from server.security.auth import create_access_token
from server.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    user_service: UserService = Depends(get_user_service),
):
    existing_user = user_service.get_user_by_username(payload.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )

    user = user_service.create_user(payload)
    access_token = create_access_token(subject=user.username, role=user.role)
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    user_service: UserService = Depends(get_user_service),
):
    user = user_service.authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token = create_access_token(subject=user.username, role=user.role)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
