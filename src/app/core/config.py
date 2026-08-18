import logging
import os
from logging.config import dictConfig
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.config import Config

from .logging import logging_config

if os.path.exists(".env"):
    config = Config(".env")
else:
    config = Config()

API_PREFIX = "/api"
VERSION = "0.1.0"
# Keep in sync with the single Alembic head; readiness fails closed on schema drift.
DATABASE_SCHEMA_REVISION = "20260817_0009"
DEBUG: bool = config("DEBUG", cast=bool, default=False)
MEMOIZATION_FLAG: bool = config("MEMOIZATION_FLAG", cast=bool, default=True)
AUTO_CREATE_TABLES: bool = config("AUTO_CREATE_TABLES", cast=bool, default=False)
MAX_UPLOAD_BYTES: int = config("MAX_UPLOAD_BYTES", cast=int, default=10 * 1024 * 1024)
DEFAULT_USERS_FILE: str | None = (
    config("DEFAULT_USERS_FILE", cast=str, default="").strip() or None
)

HOST: str = config("HOST", cast=str, default="localhost")
PORT: int = config("PORT", cast=int, default=8000)
PROJECT_NAME: str = config("PROJECT_NAME", default="Умное Расписание")

# Schedule generation
MAX_TIME_SECONDS = 900
DEFAULT_COMPONENT_TIME_SECONDS = 150
MAX_LESSON_NUMBER = 6
GENERATION_LESSONS = list(range(1, MAX_LESSON_NUMBER + 1))
GROUP_LOAD_EARLY_PRIORITY_STEP = 6
GROUP_LOAD_EARLY_PRIORITY_MULTIPLIER = 1

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
ALLOWED_HOSTS: list[str] = [
    host.strip()
    for host in config(
        "ALLOWED_HOSTS",
        cast=str,
        default="localhost,127.0.0.1,test",
    ).split(",")
    if host.strip()
]

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
sessionmaker = async_sessionmaker(engine, expire_on_commit=False)


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
