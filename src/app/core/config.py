import logging
import os
from logging.config import dictConfig
from typing import AsyncGenerator

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
AUTO_CREATE_TABLES: bool = config("AUTO_CREATE_TABLES", cast=bool, default=False)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

HOST: str = config("HOST", cast=str, default="localhost")
PORT: int = config("PORT", cast=int, default=8000)
PROJECT_NAME: str = config("PROJECT_NAME", default="Умное Расписание")

POSTGRES_HOST: str = config("POSTGRES_HOST", cast=str, default="localhost")
POSTGRES_PORT: int = config("POSTGRES_PORT", cast=int, default=5432)
POSTGRES_USER: str = config("POSTGRES_USER", cast=str, default="postgres")
POSTGRES_PASSWORD: str = config("POSTGRES_PASSWORD", cast=str, default="<PASSWORD>")
POSTGRES_DB: str = config("POSTGRES_DATABASE", cast=str, default="postgres")

DATABASE_URL: str = config(
    "DATABASE_URL",
    cast=str,
    default="sqlite+aiosqlite:///scheduler.db",
)
REDIS_URL: str = config("REDIS_URL", cast=str, default="redis://localhost:6379/0")
CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in config(
        "CORS_ORIGINS",
        cast=str,
        default="http://localhost:5173,http://localhost",
    ).split(",")
    if origin.strip()
]

BOT_TOKEN: str = config("BOT_TOKEN", cast=str, default="")

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
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

os.makedirs("logs", exist_ok=True)
dictConfig(logging_config)

# Создаем экземпляр логгера для нашего модуля
logger = logging.getLogger(__name__)
