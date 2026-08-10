import datetime

import pytest_asyncio
from core.config import AUTH_COOKIE_NAME, async_get_db
from database import DeclBase, UserAccount, UserSession
from httpx import ASGITransport, AsyncClient
from main import app
from services.auth_service import hash_password, hash_session_token
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
            "INSERT INTO alembic_version (version_num) VALUES ('20260809_0008')"
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
async def test_user(db_session: AsyncSession) -> UserAccount:
    user = UserAccount(
        username="testadmin",
        display_name="Test Administrator",
        password_hash=hash_password("CorrectPassword123!"),
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def unauthenticated_api_client(db_session: AsyncSession) -> AsyncClient:
    async def override_db():
        yield db_session

    app.dependency_overrides[async_get_db] = override_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api_client(
    db_session: AsyncSession,
    test_user: UserAccount,
) -> AsyncClient:
    async def override_db():
        yield db_session

    token = "test-session-token"
    csrf_token = "test-csrf-token"
    now = datetime.datetime.utcnow()
    db_session.add(
        UserSession(
            user_id=test_user.id,
            token_hash=hash_session_token(token),
            csrf_token=csrf_token,
            created_at=now,
            last_seen_at=now,
            expires_at=now + datetime.timedelta(hours=1),
        )
    )
    await db_session.commit()

    app.dependency_overrides[async_get_db] = override_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={AUTH_COOKIE_NAME: token},
            headers={"X-CSRF-Token": csrf_token},
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
