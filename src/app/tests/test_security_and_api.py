import importlib
from unittest.mock import AsyncMock

import pytest
import services.upload_service as upload_service
from database import ImportBatch, Stream, StreamGroup
from httpx import AsyncClient
from sqlalchemy import select, text

scheduler_routes = importlib.import_module("api.routes.scheduler")


@pytest.mark.asyncio
async def test_api_responses_include_security_headers(api_client: AsyncClient) -> None:
    response = await api_client.get("/health/live")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_readiness_checks_database_revision(
    api_client: AsyncClient, db_session
) -> None:
    ready_response = await api_client.get("/health/ready")
    assert ready_response.status_code == 200

    await db_session.execute(
        text("UPDATE alembic_version SET version_num = 'outdated'")
    )
    await db_session.commit()

    outdated_response = await api_client.get("/health/ready")
    assert outdated_response.status_code == 503


@pytest.mark.asyncio
async def test_generation_rejects_unsafe_solver_settings(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/scheduler/generate",
        json={
            "groups": ["ГР-1"],
            "holidays": [],
            "start_date": "2026-09-07",
            "end_date": "2026-09-13",
            "settings": {"solver_workers": 10_000},
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_schedule_update_rejects_invalid_lesson_number(
    api_client: AsyncClient,
) -> None:
    response = await api_client.patch(
        "/api/v1/scheduler/schedule/1", json={"lesson_number": 8}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_availability_rejects_invalid_lesson_number(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/reference/availability",
        json={
            "teacher_id": 1,
            "rule_kind": "unavailable",
            "recurrence": "weekly",
            "weekday": 0,
            "lesson_start": 8,
            "lesson_end": 8,
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_limit_is_enforced(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(upload_service, "MAX_UPLOAD_BYTES", 16)

    response = await api_client.post(
        "/api/v1/scheduler/import/streams",
        files={"file": ("streams.csv", b"x" * 17, "text/csv")},
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_stream_csv_upload_sanitizes_filename_and_imports_data(
    api_client: AsyncClient, db_session
) -> None:
    csv_content = """Мероприятие;Вид потока;Преподаватель;Группа
Математика;Л;Иванов И.И.;ГР-1 [20]
""".encode()

    response = await api_client.post(
        "/api/v1/scheduler/import/streams",
        files={"file": ("../../streams.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    batch = (await db_session.execute(select(ImportBatch))).scalar_one()
    assert batch.filename == "streams.csv"
    assert (await db_session.execute(select(Stream))).scalar_one()
    assert (await db_session.execute(select(StreamGroup))).scalar_one()

    delete_response = await api_client.delete(
        f"/api/v1/scheduler/import/history/{batch.id}"
    )
    assert delete_response.status_code == 200


@pytest.mark.asyncio
async def test_teacher_import_reports_missing_columns(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/scheduler/teachers/import",
        files={"file": ("teachers.csv", b"wrong;columns\n1;2\n", "text/csv")},
    )

    assert response.status_code == 400
    assert "Missing required columns" in response.json()["detail"]


@pytest.mark.asyncio
async def test_teacher_import_reports_invalid_restriction(
    api_client: AsyncClient, db_session
) -> None:
    csv_content = """ФИО преподавателя;Режим;Регулярные окна (День_Пара)
Иванов И.И.;blacklist;9-2
""".encode()

    response = await api_client.post(
        "/api/v1/scheduler/teachers/import",
        files={"file": ("teachers.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 400
    assert "Invalid recurring restriction" in response.json()["detail"]


@pytest.mark.asyncio
async def test_failed_stream_import_removes_saved_upload(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    csv_content = """Мероприятие;Вид потока;Преподаватель;Группа
Математика;Л;Иванов И.И.;ГР-1 [20]
""".encode()
    monkeypatch.setattr(scheduler_routes, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(
        scheduler_routes.ScheduleService,
        "import_streams",
        AsyncMock(side_effect=RuntimeError("simulated import failure")),
    )

    with pytest.raises(RuntimeError, match="simulated import failure"):
        await api_client.post(
            "/api/v1/scheduler/import/streams",
            files={"file": ("streams.csv", csv_content, "text/csv")},
        )

    assert list(tmp_path.iterdir()) == []
