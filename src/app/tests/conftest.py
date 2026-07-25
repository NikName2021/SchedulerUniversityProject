import pytest_asyncio
from core.config import async_get_db
from database import DeclBase
from httpx import ASGITransport, AsyncClient
from main import app
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
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        await conn.run_sync(DeclBase.metadata.create_all)
        await conn.exec_driver_sql(
            "CREATE TABLE alembic_version "
            "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
        )
        await conn.exec_driver_sql(
            "INSERT INTO alembic_version (version_num) "
            "VALUES ('20260720_0006')"
        )

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


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncClient:
    async def override_db():
        yield db_session

    app.dependency_overrides[async_get_db] = override_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
