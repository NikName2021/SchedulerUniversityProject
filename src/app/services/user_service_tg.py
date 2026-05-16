from datetime import datetime

from database import Settings, User
from fastapi import HTTPException
from helpers import create_jwt_token, create_refresh_token
from repositories import FavoritesDTO, SettingDTO, UserDTO, UserRepository
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import JSONResponse


class UserService:
    @staticmethod
    def _form_user(user: User) -> dict:
        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "sub_start": user.sub_start.strftime("%d.%m.%y %H:%M")
            if user.sub_end > datetime.now()
            else "",
            "sub_end": user.sub_end.strftime("%d.%m.%y %H:%M")
            if user.sub_end > datetime.now()
            else "",
            "subscription": bool(user.sub_end > datetime.now()),
            "last_login": user.last_login.strftime("%d.%m.%y %H:%M"),
            "created_date": user.created_date.strftime("%d.%m.%y %H:%M"),
            "notification": user.notification,
        }

    @staticmethod
    def _form_setting(settings: Settings) -> dict:
        return {
            "id": settings.id,
            "type_site": settings.type_site,
        }

    @staticmethod
    def _form_favorite(favorite) -> dict:
        return {
            "id": favorite.id,
            "created_date": favorite.created_date.strftime("%d.%m.%y %H:%M"),
        }

    @staticmethod
    async def get_or_create_user(user_data: dict, db: AsyncSession) -> JSONResponse:
        user = await UserRepository.get_user(user_data["user_id"], db)

        if user:
            user.last_login = datetime.now()
            if user_data.get("username"):
                user.username = user_data["username"]
            await db.commit()
            await db.refresh(user, ["settings"])
            settings = user.settings
        else:
            user_dto = UserDTO(
                telegram_id=user_data["user_id"],
                username=user_data.get("username"),
                chat_id=user_data.get("chat_id", 2),
            )

            user = await UserRepository.create(user_dto, db)
            settings_dto = SettingDTO(user_id=user.id)
            settings = await UserRepository.create_settings(settings_dto, db)

        answer = {
            "auth": {
                "access_token": create_jwt_token(user_data),
                "refresh_token": create_refresh_token(user_data, user.id),
                "token_type": "bearer",
            },
            "information": {
                "user": UserService._form_user(user),
                "settings": UserService._form_setting(settings),
            },
        }

        return JSONResponse(content=answer, status_code=200)

    @staticmethod
    async def get_user_settings(user: User, db: AsyncSession) -> JSONResponse:
        settings = await UserRepository.get_user_settings(user.id, db)

        answer = {
            "user": UserService._form_user(user),
            "settings": UserService._form_setting(settings),
        }

        return JSONResponse(content=answer, status_code=200)

    @staticmethod
    async def update_user_settings(user: User, data, db: AsyncSession) -> JSONResponse:
        settings = await UserRepository.get_user_settings(user.id, db)
        """Нехорошо"""
        if data.type_site not in [0, 1]:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Неверный тип type_site",
            )

        settings.type_site = data.type_site
        await db.commit()
        await db.refresh(settings)

        answer = {
            "user": UserService._form_user(user),
            "settings": UserService._form_setting(settings),
        }
        return JSONResponse(content=answer, status_code=200)

    @staticmethod
    async def get_favorites(user: User, db: AsyncSession) -> JSONResponse:
        favorites = await UserRepository.get_user_favorites(user.id, db)

        answer = {
            "favorites": [
                UserService._form_favorite(favorite) for favorite in favorites
            ]
        }
        return JSONResponse(content=answer, status_code=200)

    @staticmethod
    async def check_favorite(
        user: User, league_id: int, db: AsyncSession
    ) -> JSONResponse:
        favorite = await UserRepository.get_user_favorite_match(user.id, league_id, db)

        answer = {"favorite": bool(favorite), "league_id": int(league_id)}
        return JSONResponse(content=answer, status_code=200)

    @staticmethod
    async def create_delete_favorite(
        user: User, league_id: int, db: AsyncSession
    ) -> JSONResponse:
        favorite = await UserRepository.get_user_favorite_match(user.id, league_id, db)
        if not favorite:
            favorite_dto = FavoritesDTO(league_id=league_id, user_id=user.id)
            await UserRepository.create_favorite(favorite_dto, db)
            status = "create"
        else:
            await db.delete(favorite)
            await db.commit()
            status = "delete"

        answer = {"status": status, "code": 1}
        return JSONResponse(content=answer, status_code=200)
