import pytest_asyncio
from database import DeclBase
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Используем отдельный URL для тестовой БД
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"  # <-- ВАШ URL


# Убедитесь, что переменная окружения установлена, или жестко задайте URL
# os.environ["TEST_DATABASE_URL"] = TEST_DATABASE_URL


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    """
    Фикстура, которая создает чистую БД для каждого теста.
    """
    # Создаем движок специально для тестов
    engine = create_async_engine(TEST_DATABASE_URL)

    # Создаем все таблицы
    async with engine.begin() as conn:
        await conn.run_sync(DeclBase.metadata.create_all)

    # Создаем сессию
    TestAsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with TestAsyncSessionLocal() as session:
        yield session

    # Удаляем все таблицы после завершения теста
    async with engine.begin() as conn:
        await conn.run_sync(DeclBase.metadata.drop_all)

    await engine.dispose()
