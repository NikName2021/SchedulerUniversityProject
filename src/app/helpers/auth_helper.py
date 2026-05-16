import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta

import jwt
from core.config import BOT_TOKEN, SECRET_KEY, async_get_db
from database import User
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from repositories import UserRepository
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

JWT_EXPIRATION = 6
JWT_ALGORITHM = "HS256"

security = HTTPBearer()


def verify_telegram_hash(tg_web_app_data: dict) -> dict:
    # Получаем данные пользователя и hash
    user = tg_web_app_data.get("user", {})
    auth_date = tg_web_app_data.get("auth_date")
    received_hash = tg_web_app_data.get("hash")

    # if not all([user, auth_date, received_hash]):
    #     raise HTTPException(
    #         status_code=400,
    #         detail="Missing required Telegram data"
    #     )

    # Формируем строку для проверки
    check_arr = []
    for key, value in sorted(tg_web_app_data.items()):
        if key != "hash":
            if isinstance(value, dict):
                check_arr.append(f"{key}={json.dumps(value)}")
            else:
                check_arr.append(f"{key}={value}")

    data_check_string = "\n".join(check_arr)

    # Создаем secret key
    secret_key = hmac.new(
        "WebAppData".encode(), BOT_TOKEN.encode(), hashlib.sha256
    ).digest()

    # Вычисляем hash
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    # if calculated_hash != received_hash:
    #     raise HTTPException(
    #         status_code=401,
    #         detail="Invalid Telegram hash"
    #     )

    # Возвращаем данные пользователя
    return {
        "user_id": user.get("id"),
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
    }


def create_refresh_token(user_data: dict, user_id_db: int) -> str:
    token = create_jwt_token(user_data, type_access="refresh")
    return token


def create_jwt_token(user_data: dict, type_access="access") -> str:
    """Создание JWT токена"""

    payload = {
        "user_id": user_data["user_id"],
        "type": type_access,
        "username": user_data["username"],
        "jti": str(uuid.uuid4()),
        "start": int(datetime.now().timestamp()),
    }
    expiration = (
        int((datetime.now() + timedelta(hours=JWT_EXPIRATION)).timestamp())
        if type_access == "access"
        else None
    )
    payload["exp"] = expiration

    token = jwt.encode(payload, str(SECRET_KEY), algorithm=JWT_ALGORITHM)

    return token


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(async_get_db),
) -> User:
    try:
        payload = jwt.decode(
            credentials.credentials, str(SECRET_KEY), algorithms=[JWT_ALGORITHM]
        )

        telegram_id = payload.get("user_id")
        if telegram_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        user = await UserRepository.get_user(telegram_id, db)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_active_subscription(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Зависимость, которая проверяет наличие активной подписки у пользователя.
    Она зависит от `get_current_user`, чтобы сначала получить пользователя.
    """
    if not current_user.sub_end or current_user.sub_end <= datetime.now():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется активная подписка для доступа к этому ресурсу.",
        )
    return current_user
