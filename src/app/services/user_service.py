import jwt
from core.config import ALGORITHM, SECRET_KEY
from database import IssuedJWTToken, Role, User
from fastapi import HTTPException, status
from helpers import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from repositories import AuthRepository
from schemas import Token, UserCreate, UserLogin, UserResponse


class AuthService:
    def __init__(self, repo: AuthRepository) -> None:
        self.repo = repo

    async def register_user(self, user_data: UserCreate) -> User:
        existing_user = await self.repo.get_user_by_email_or_username(
            user_data.email, user_data.username
        )
        if existing_user:
            if existing_user.email == user_data.email:
                raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
            raise HTTPException(status_code=400, detail="Username уже занят")

        new_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hash_password(user_data.password),
            role=Role.USER,
        )
        return await self.repo.create_user(new_user)

    async def authenticate_user(self, user_data: UserLogin) -> Token:
        user = await self.repo.get_user_by_email(user_data.email)

        if not user or not verify_password(user_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await self._generate_tokens(user)

    async def refresh_token(self, refresh_token_str: str) -> Token:
        try:
            payload = jwt.decode(refresh_token_str, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный refresh token",
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Это не refresh token"
            )

        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Некорректный токен")

        token_obj = await self.repo.get_valid_refresh_token(refresh_token_str, user_id)
        if not token_obj:
            raise HTTPException(
                status_code=401, detail="Refresh token отозван или истёк"
            )

        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        return await self._generate_tokens(user)

    async def _generate_tokens(self, user: User) -> Token:
        payload = {"user_id": user.id, "role": user.role.value}

        access_token = create_access_token(payload)
        refresh_token = create_refresh_token(payload)

        token_obj = IssuedJWTToken(user_id=user.id, jti=refresh_token)
        await self.repo.save_token(token_obj)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        )
