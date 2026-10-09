from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.schemas.user import User
from server.schemas.auth import RegisterRequest
from server.security.password import hash_password, verify_password


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        return self.db.scalars(stmt).first()

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        return self.db.scalars(stmt).first()

    def create_user(self, payload: RegisterRequest) -> User:
        """ایجاد کاربر جدید با پسورد هش‌شده"""
        hashed_pwd = hash_password(payload.password)
        db_user = User(
            username=payload.username,
            hashed_password=hashed_pwd,
            role=payload.role or "user",
            is_active=True,
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def authenticate_user(
        self, username: str, password: str
    ) -> Optional[User]:
        user = self.get_user_by_username(username)
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
