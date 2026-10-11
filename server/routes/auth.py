import secrets

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.exc import IntegrityError

from server.dependencies import get_current_user, get_user_service
from server.schemas.user import User
from server.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    VerifyCodeRequest,
)
from server.security.auth import create_access_token
from server.security.password import verify_password
from server.services.email_service import send_verification_email
from server.services.user_service import UserService


router = APIRouter(prefix="/auth", tags=["auth"])


def generate_verification_code() -> str:

    return str(100000 + secrets.randbelow(900000))


@router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
)
def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    user_service: UserService = Depends(get_user_service),
):
    email = str(payload.email).strip().lower()
    existing_email_user = user_service.get_user_by_email(email)

    if existing_email_user:
        if existing_email_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="این ایمیل قبلاً ثبت و تأیید شده است.",
            )

        if existing_email_user.username != payload.username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="برای این ایمیل ثبت‌نام تأییدنشده‌ای با نام کاربری دیگری وجود دارد.",
            )

        code = generate_verification_code()
        user_service.update_verify_code(existing_email_user, code)
        target_email = existing_email_user.email

    else:
        existing_username_user = user_service.get_user_by_username(payload.username)

        if existing_username_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="این نام کاربری قبلاً ثبت شده است.",
            )

        code = generate_verification_code()

        try:
            user = user_service.create_user(
                payload=payload,
                verify_code=code,
            )
        except IntegrityError:

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="این ایمیل یا نام کاربری قبلاً ثبت شده است.",
            )

        target_email = user.email

    background_tasks.add_task(
        send_verification_email,
        target_email,
        code,
    )

    return {
        "message": "کد تأیید به ایمیل شما ارسال شد."
    }


@router.post("/verify")
def verify_email(
    payload: VerifyCodeRequest,
    user_service: UserService = Depends(get_user_service),
):
    user = user_service.get_user_by_email(str(payload.email))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کاربری با این ایمیل پیدا نشد.",
        )

    if user.is_verified:
        return {"message": "این حساب قبلاً تأیید شده است."}

    if not user.verify_code or not secrets.compare_digest(
        user.verify_code,
        payload.code,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="کد تأیید نادرست است.",
        )

    user_service.verify_user(user)

    return {"message": "ایمیل با موفقیت تأیید شد."}


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    user_service: UserService = Depends(get_user_service),
):
    user = user_service.authenticate_user(
        username_or_email=payload.username_or_email,
        password=payload.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری/ایمیل یا کلمه عبور اشتباه است.",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ابتدا ایمیل خود را با کد ارسال‌شده تأیید کنید.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این حساب کاربری غیرفعال است.",
        )

    access_token = create_access_token(
        subject=user.username,
        role=user.role,
    )

    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
