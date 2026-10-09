from typing import Generator
from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from server.database import SessionLocal
from server.security.auth import verify_access_token
from server.services.user_service import UserService
from server.database import get_db, SessionLocal

# برای خواندن خودکار توکن از هدر Authorization در روت‌های HTTP
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ۱. تزریق سشن دیتابیس به روت‌ها
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ۲. تزریق سرویس کاربر همراه با دیتابیس
def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


# ۳. دسترسی به مدل پیش‌بینی
def get_predictor(request: Request):
    predictor = getattr(request.app.state, "predictor", None)
    if predictor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Predictor is not ready",
        )
    return predictor


# ۴. احراز هویت برای اندپوینت‌های HTTP (با هدر Authorization: Bearer ...)
def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service),
):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = verify_access_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = user_service.get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    return user


# ۵. احراز هویت اختصاصی برای وب‌سوکت (Native WebSocket با توکن در Query Param)
async def get_current_user_from_ws(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return None

    username = verify_access_token(token)
    if not username:
        await websocket.close(code=4401, reason="Invalid token")
        return None

    # باز کردن سشن مستقل موقت برای وب‌سوکت
    db = SessionLocal()
    try:
        user_service = UserService(db)
        user = user_service.get_user_by_username(username)
        if not user:
            await websocket.close(code=4401, reason="User not found")
            return None

        if not user.is_active:
            await websocket.close(code=4403, reason="Inactive user")
            return None

        return user
    finally:
        db.close()
