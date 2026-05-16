from database import IssuedJWTToken, User
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class AuthRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_email_or_username(
        self, email: str, username: str
    ) -> User | None:
        query = select(User).where(or_(User.email == email, User.username == username))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_user(self, user: User) -> User:
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def save_token(self, token: IssuedJWTToken) -> None:
        self.db.add(token)
        await self.db.commit()

    async def get_valid_refresh_token(
        self, token_jti: str, user_id: int
    ) -> IssuedJWTToken | None:
        query = select(IssuedJWTToken).where(
            IssuedJWTToken.jti == token_jti,
            IssuedJWTToken.user_id == user_id,
            IssuedJWTToken.revoked.is_(False),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
