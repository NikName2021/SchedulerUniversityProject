def get_db_path(user: str, host: str, port: int, database: str, password: str) -> str:
    return "sqlite+aiosqlite:///scheduler.db"
