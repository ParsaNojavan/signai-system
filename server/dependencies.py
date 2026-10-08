from fastapi import HTTPException, Request, WebSocket, status

from server.security.auth import verify_access_token
from server.services.user_service import UserService


user_service = UserService()


def get_predictor(request: Request):
    predictor = getattr(request.app.state, "predictor", None)
    if predictor is None:
        raise HTTPException(status_code=503, detail="Predictor is not ready")
    return predictor


def get_current_user_from_token(token: str):
    username = verify_access_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = user_service.get_user(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_current_user_from_ws(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return None

    username = verify_access_token(token)
    if not username:
        await websocket.close(code=4401, reason="Invalid or expired token")
        return None

    user = user_service.get_user(username)
    if not user:
        await websocket.close(code=4401, reason="User not found")
        return None

    if not user.is_active:
        await websocket.close(code=4403, reason="Inactive user")
        return None

    return user
