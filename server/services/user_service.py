from dataclasses import dataclass
from typing import Optional

from server.security.password import hash_password, verify_password


@dataclass
class User:
    username: str
    hashed_password: str
    is_active: bool = True


class UserService:
    def __init__(self):
        self._users = {
            "admin": User(
                username="admin",
                hashed_password=hash_password("admin123"),
                is_active=True,
            ),
            "parsa": User(
                username="parsa",
                hashed_password=hash_password("parsa123"),
                is_active=True,
            ),
        }

    def get_user(self, username: str) -> Optional[User]:
        return self._users.get(username)

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        user = self.get_user(username)
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
