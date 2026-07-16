import os


def get_db_path(user: str, host: str, port: int, database: str, password: str) -> str:
    if os.getenv("POSTGRES_HOST"):
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    return "sqlite+aiosqlite:///scheduler.db"

