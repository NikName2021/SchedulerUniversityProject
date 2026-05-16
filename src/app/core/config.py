import logging
import os
from logging.config import dictConfig
from typing import AsyncGenerator

from database.db_session import get_db_path
from fastapi.security import HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.config import Config
from starlette.datastructures import Secret

from .logging import logging_config

if os.path.exists(".env"):
    config = Config(".env")
else:
    config = Config()

API_PREFIX = "/api"
VERSION = "0.1.0"
DEBUG: bool = config("DEBUG", cast=bool, default=False)
SECRET_KEY: Secret = config("SECRET_KEY", cast=Secret, default="")
MEMOIZATION_FLAG: bool = config("MEMOIZATION_FLAG", cast=bool, default=True)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

HOST: str = config("HOST", cast=str, default="localhost")
PORT: int = config("PORT", cast=int, default=8000)
PROJECT_NAME: str = config("PROJECT_NAME", default="pregnancy-model")

POSTGRES_HOST: str = config("POSTGRES_HOST", cast=str, default="localhost")
POSTGRES_PORT: int = config("POSTGRES_PORT", cast=int, default=5432)
POSTGRES_USER: str = config("POSTGRES_USER", cast=str, default="postgres")
POSTGRES_PASSWORD: str = config("POSTGRES_PASSWORD", cast=str, default="<PASSWORD>")
POSTGRES_DB: str = config("POSTGRES_DATABASE", cast=str, default="postgres")

BOT_TOKEN: str = config("BOT_TOKEN", cast=str, default="")

engine = create_async_engine(
    get_db_path(
        POSTGRES_USER, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_PASSWORD
    )
)
sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

security = HTTPBearer()


async def async_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker() as db:
        yield db


# logging configuration
# LOGGING_LEVEL = logging.DEBUG if DEBUG else logging.INFO
# logging.basicConfig(
#     handlers=[InterceptHandler(level=LOGGING_LEVEL)], level=LOGGING_LEVEL
# )
# logger.configure(handlers=[{"sink": sys.stderr, "level": LOGGING_LEVEL}])

dictConfig(logging_config)

# Создаем экземпляр логгера для нашего модуля
logger = logging.getLogger(__name__)
