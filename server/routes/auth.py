from fastapi import APIRouter, HTTPException, status

from server.schemas.auth import LoginRequest, TokenResponse
from server.security.auth import create_access_token
from server.dependencies import user_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    user = user_service.authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token = create_access_token(user.username)
    return TokenResponse(access_token=access_token)
