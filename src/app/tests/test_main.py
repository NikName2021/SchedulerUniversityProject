import main
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


@pytest.mark.asyncio
async def test_application_lifespan_starts_without_legacy_event_api(
    monkeypatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    empty_database_sessions = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(main, "AUTO_CREATE_TABLES", False)
    monkeypatch.setattr(main, "DEFAULT_USERS_FILE", None)
    monkeypatch.setattr(main, "sessionmaker", empty_database_sessions)
    application = main.get_application()

    try:
        async with application.router.lifespan_context(application):
            pass
    finally:
        await engine.dispose()
