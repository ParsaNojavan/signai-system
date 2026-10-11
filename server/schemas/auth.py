from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr = Field(..., description="آدرس ایمیل معتبر جهت ارسال کد تایید")
    password: str = Field(..., min_length=6, max_length=128)

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="کد تایید ۶ رقمی عددی",
    )
class LoginRequest(BaseModel):
    username_or_email: str = Field(
        ..., min_length=3, max_length=255, description="نام کاربری یا ایمیل"
    )
    password: str = Field(..., min_length=3, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    role: str
    is_verified: bool
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TokenPayload(BaseModel):
    sub: str
    role: str = "user"
    exp: int
