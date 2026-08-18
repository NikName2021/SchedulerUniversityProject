import main
import pytest


@pytest.mark.asyncio
async def test_application_lifespan_starts_without_legacy_event_api(
    monkeypatch,
) -> None:
    monkeypatch.setattr(main, "AUTO_CREATE_TABLES", False)
    monkeypatch.setattr(main, "DEFAULT_USERS_FILE", None)
    application = main.get_application()

    async with application.router.lifespan_context(application):
        pass
