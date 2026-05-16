from datetime import datetime

from database import IssuedJWTToken, Settings, User
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

"""class User(DeclBase):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False)
    username = Column(String)
    chat_id = Column(BigInteger, nullable=False)
    notification = Column(Boolean, default=False)
    sub_start = Column(DateTime, nullable=True)
    sub_end = Column(DateTime, nullable=True)
    created_date = Column(DateTime, default=datetime.datetime.now)"""


class UserDTO(BaseModel):
    telegram_id: int | None = None
    username: str | None = None
    chat_id: int = None
    sub_start: datetime | None = None
    sub_end: datetime | None = None


class SettingDTO(BaseModel):
    user_id: int | None = None
    type_site: int = 1


class FavoritesDTO(BaseModel):
    user_id: int
    league_id: int


class IssuedJWTTokenDTO(BaseModel):
    user_id: int
    jti: str


class UserRepository:
    @staticmethod
    async def get_user(telegram_id: int, session: AsyncSession):
        stmt = (
            select(User)
            .options(selectinload(User.settings))
            .where(User.telegram_id == telegram_id)
        )
        user = await session.execute(stmt)
        return user.scalar()

    @staticmethod
    async def create(user_data: UserDTO, session: AsyncSession) -> User:
        user = User(**user_data.model_dump())
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def get_user_settings(user_id: int, session: AsyncSession):
        stmt = select(Settings).where(Settings.user_id == user_id)
        settings = await session.execute(stmt)
        return settings.scalar()

    @staticmethod
    async def create_settings(
        settings_dto: SettingDTO, session: AsyncSession
    ) -> Settings:
        setting = Settings(**settings_dto.model_dump())
        session.add(setting)
        await session.commit()
        await session.refresh(setting)
        return setting

    @staticmethod
    async def create_refresh(
        jwt_dto: IssuedJWTTokenDTO, session: AsyncSession
    ) -> IssuedJWTToken:
        jwt = IssuedJWTToken(**jwt_dto.model_dump())
        session.add(jwt)
        await session.commit()
        await session.refresh(jwt)
        return jwt
