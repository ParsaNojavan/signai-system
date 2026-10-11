from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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

    def get_user_by_email(self, email: str) -> Optional[User]:
        normalized_email = email.strip().lower()
        stmt = select(User).where(User.email == normalized_email)
        return self.db.scalars(stmt).first()

    def get_user_by_login(self, username_or_email: str) -> Optional[User]:
        identifier = username_or_email.strip()

        if "@" in identifier:
            return self.get_user_by_email(identifier)

        return self.get_user_by_username(identifier)

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        return self.db.scalars(stmt).first()

    def create_user(
        self,
        payload: RegisterRequest,
        verify_code: str,
    ) -> User:
        db_user = User(
            username=payload.username,
            email=str(payload.email).strip().lower(),
            hashed_password=hash_password(payload.password),
            role="user",  # نقش از درخواست کاربر پذیرفته نمی‌شود
            is_active=True,
            is_verified=False,
            verify_code=verify_code,
        )

        self.db.add(db_user)

        try:
            self.db.commit()
            self.db.refresh(db_user)
        except IntegrityError:
            self.db.rollback()
            raise

        return db_user

    def update_verify_code(self, user: User, code: str) -> None:
        user.verify_code = code
        self.db.commit()

    def verify_user(self, user: User) -> None:
        user.is_verified = True
        user.verify_code = None
        self.db.commit()

    def authenticate_user(
        self,
        username_or_email: str,
        password: str,
    ) -> Optional[User]:
        user = self.get_user_by_login(username_or_email)

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        return user
