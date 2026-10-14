import datetime
from contextlib import AsyncExitStack
from types import SimpleNamespace

import pytest
import pytest_asyncio
from api.routes import scheduler
from core.config import async_get_db
from core.constants import AUTH_COOKIE_NAME
from database import (
    AcademicPeriod,
    Department,
    FileType,
    GenerationComponent,
    GenerationIssue,
    GenerationTask,
    ImportBatch,
    PlanningWeek,
    RuleProfile,
    ScheduleEntry,
    Stream,
    StreamGroup,
    Teacher,
    UserAccount,
    UserSession,
)
from database.workspace import WorkspaceAccessError, bind_task_workspace, bind_workspace
from httpx import ASGITransport, AsyncClient
from main import app
from services.auth_service import hash_session_token
from services.generation_lifecycle_service import GenerationLifecycleService
from services.scalable_generation_service import ScalableGenerationService
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest_asyncio.fixture
async def spaces(db_session, test_user):
    other_user = UserAccount(
        username="other", display_name="Other", password_hash="unused", role="operator"
    )
    db_session.add(other_user)
    await db_session.commit()
    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    users = [test_user, other_user]
    seeds = []
    for user in users:
        async with factory() as db:
            bind_workspace(db, user.id)
            batch = ImportBatch(filename="same.csv", file_type=FileType.STREAMS)
            teacher = Teacher(name="Same teacher")
            department = Department(name="Same department", code="SAME")
            profile = RuleProfile(name="Same profile", is_default=True)
            period = AcademicPeriod(
                name="Semester",
                starts_on=datetime.date(2026, 9, 7),
                ends_on=datetime.date(2026, 9, 13),
            )
            db.add_all([batch, teacher, department, profile, period])
            await db.flush()
            week = PlanningWeek(
                period_id=period.id,
                sequence_number=1,
                starts_on=period.starts_on,
                ends_on=period.ends_on,
            )
            stream = Stream(
                import_batch_id=batch.id,
                teacher_id=teacher.id,
                event_name=f"Subject {user.id}",
                stream_type="Лекция",
            )
            db.add_all([week, stream])
            await db.flush()
            task = GenerationTask(
                planning_week_id=week.id,
                groups_json='["A"]',
                holidays_json="[]",
                settings_json="{}",
                status="success",
                semester_batch_id="same-batch",
            )
            db.add(task)
            await db.flush()
            entry = ScheduleEntry(
                task_id=task.id,
                planning_week_id=week.id,
                source_stream_id=stream.id,
                teacher_id=teacher.id,
                group_name="A",
                event_name=stream.event_name,
                stream_type="Лекция",
                date=datetime.datetime(2026, 9, 7),
                lesson_number=1,
            )
            db.add_all(
                [
                    entry,
                    StreamGroup(stream_id=stream.id, group_name="A", group_size=20),
                    GenerationComponent(task_id=task.id, component_key="one"),
                    GenerationIssue(
                        task_id=task.id, kind="test", message="Private issue"
                    ),
                    UserSession(
                        user_id=user.id,
                        token_hash=hash_session_token(f"token-{user.id}"),
                        csrf_token=f"csrf-{user.id}",
                        expires_at=datetime.datetime.utcnow()
                        + datetime.timedelta(hours=1),
                    ),
                ]
            )
            await db.commit()
            seeds.append(
                SimpleNamespace(
                    user=user,
                    batch=batch,
                    teacher=teacher,
                    task=task,
                    entry=entry,
                    stream=stream,
                    week=week,
                    period=period,
                    department=department,
                    profile=profile,
                )
            )

    async def override_db():
        async with factory() as db:
            yield db

    app.dependency_overrides[async_get_db] = override_db
    try:
        async with AsyncExitStack() as stack:
            for seed in seeds:
                seed.client = await stack.enter_async_context(
                    AsyncClient(
                        transport=ASGITransport(app=app),
                        base_url="http://test",
                        cookies={AUTH_COOKIE_NAME: f"token-{seed.user.id}"},
                        headers={"X-CSRF-Token": f"csrf-{seed.user.id}"},
                    )
                )
            yield SimpleNamespace(first=seeds[0], second=seeds[1], factory=factory)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_lists_aggregates_and_summaries_are_personal_even_for_admin(spaces):
    for own in [spaces.first, spaces.second]:
        client = own.client
        for url, expected_id in [
            ("scheduler/tasks", own.task.id),
            ("scheduler/import/history", own.batch.id),
            ("scheduler/schedule", own.entry.id),
            ("reference/departments", own.department.id),
            ("reference/rule-profiles", own.profile.id),
            ("planning/periods", own.period.id),
        ]:
            response = await client.get(f"/api/v1/{url}")
            assert response.status_code == 200, response.text
            assert [row["id"] for row in response.json()] == [expected_id]
            assert response.headers["cache-control"] == "no-store"
        stats = (await client.get("/api/v1/scheduler/stats")).json()
        assert stats["total_streams"] == stats["total_teachers"] == 1
        summary = await client.post(
            "/api/v1/scheduler/subjects-summary",
            json={"groups": ["A"], "types": ["Лекция"]},
        )
        assert summary.json() == {"Общее": [own.stream.event_name]}
        summary_get = await client.get(
            "/api/v1/scheduler/subjects-summary",
            params={"groups": "A", "types": "Лекция"},
        )
        assert summary_get.json() == summary.json()
        batch = await client.get(
            "/api/v1/scheduler/schedule?semester_batch_id=same-batch"
        )
        assert [row["id"] for row in batch.json()] == [own.entry.id]


@pytest.mark.asyncio
async def test_foreign_ids_cannot_read_change_delete_or_export(spaces):
    for own, foreign in [(spaces.first, spaces.second), (spaces.second, spaces.first)]:
        for method, url, payload in [
            ("GET", f"scheduler/tasks/{foreign.task.id}/diagnostics", None),
            ("GET", f"scheduler/tasks/{foreign.task.id}/components", None),
            ("GET", f"scheduler/schedule/{foreign.entry.id}/details", None),
            ("GET", f"planning/periods/{foreign.period.id}/weeks", None),
            ("GET", f"planning/weeks/{foreign.week.id}/demands", None),
            ("PATCH", f"scheduler/schedule/{foreign.entry.id}", {"lesson_number": 2}),
            ("PATCH", f"scheduler/streams/{foreign.stream.id}", {"is_ignored": True}),
            ("DELETE", f"scheduler/tasks/{foreign.task.id}", None),
            ("DELETE", f"scheduler/import/history/{foreign.batch.id}", None),
            (
                "GET",
                f"scheduler/import/history/{foreign.batch.id}/download",
                None,
            ),
            ("POST", f"scheduler/tasks/{foreign.task.id}/cancel", None),
            ("POST", f"scheduler/tasks/{foreign.task.id}/retry", None),
            ("POST", f"scheduler/tasks/{foreign.task.id}/archive", None),
            ("POST", f"scheduler/tasks/{foreign.task.id}/publish", None),
            ("GET", f"scheduler/export?task_id={foreign.task.id}", None),
        ]:
            response = await own.client.request(method, f"/api/v1/{url}", json=payload)
            assert response.status_code == 404, (url, response.text)
        response = await own.client.get(
            f"/api/v1/scheduler/schedule?task_id={foreign.task.id}"
        )
        assert response.json() == []
        response = await own.client.patch(
            f"/api/v1/reference/teachers/{own.teacher.id}",
            json={"department_id": foreign.department.id},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_bulk_operations_and_batch_deletion_stay_in_workspace(spaces):
    async with spaces.factory() as db:
        bind_workspace(db, spaces.first.user.id)
        await db.execute(update(RuleProfile).values(is_default=False))
        await db.execute(delete(GenerationIssue))
        await db.commit()
    response = await spaces.first.client.delete(
        "/api/v1/scheduler/semester-batches/same-batch"
    )
    assert response.status_code == 204
    async with spaces.factory() as db:
        bind_workspace(db, spaces.second.user.id)
        assert await db.get(GenerationTask, spaces.second.task.id) is not None
        assert (await db.get(RuleProfile, spaces.second.profile.id)).is_default
        assert await db.scalar(select(func.count(GenerationIssue.id))) == 1


@pytest.mark.asyncio
async def test_workspace_names_and_generation_locks_are_independent(spaces):
    for own in [spaces.first, spaces.second]:
        async with spaces.factory() as db:
            bind_workspace(db, own.user.id)
            task = await GenerationLifecycleService.reserve_task(
                db,
                groups=["A"],
                holidays=[],
                settings={},
                planning_week_id=None,
                start_date=datetime.datetime(2026, 9, 7),
                end_date=datetime.datetime(2026, 9, 13),
            )
            assert task.version_number == 1
            assert task.owner_id == own.user.id
            with pytest.raises(RuntimeError, match="already running"):
                await GenerationLifecycleService.reserve_task(
                    db,
                    groups=["A"],
                    holidays=[],
                    settings={},
                    planning_week_id=None,
                    start_date=task.start_date,
                    end_date=task.end_date,
                )


@pytest.mark.asyncio
async def test_publication_catalog_is_shared_but_source_remains_private(spaces):
    own = spaces.first
    response = await own.client.post(f"/api/v1/scheduler/tasks/{own.task.id}/publish")
    assert response.status_code == 200

    catalog = await spaces.second.client.get("/api/v1/scheduler/publications")
    assert catalog.status_code == 200
    [published] = catalog.json()
    assert published["owner_display_name"] == own.user.display_name
    assert published["can_edit"] is False
    assert published["source_task_id"] is None
    assert f"#{own.task.id}" not in published["title"]

    detail = await spaces.second.client.get(
        f"/api/v1/scheduler/publications/{published['id']}"
    )
    assert detail.status_code == 200
    entry = detail.json()["entries"][0]
    assert entry["event_name"] == own.stream.event_name
    assert entry["id"] == 1
    assert set(entry) == {
        "id",
        "group_name",
        "event_name",
        "stream_type",
        "teacher",
        "room_id",
        "date",
        "lesson_number",
    }

    [owner_view] = (await own.client.get("/api/v1/scheduler/publications")).json()
    assert owner_view["can_edit"] is True
    assert owner_view["source_task_id"] == own.task.id

    private = await spaces.second.client.get(
        f"/api/v1/scheduler/tasks/{own.task.id}/diagnostics"
    )
    assert private.status_code == 404


@pytest.mark.asyncio
async def test_owner_can_edit_published_schedule_and_catalog_updates(spaces):
    own = spaces.first
    await own.client.post(f"/api/v1/scheduler/tasks/{own.task.id}/publish")
    publication = (
        await spaces.second.client.get("/api/v1/scheduler/publications")
    ).json()[0]

    response = await own.client.patch(
        f"/api/v1/scheduler/schedule/{own.entry.id}",
        json={"lesson_number": 2},
    )
    assert response.status_code == 200, response.text

    detail = await spaces.second.client.get(
        f"/api/v1/scheduler/publications/{publication['id']}"
    )
    assert detail.status_code == 200
    assert detail.json()["entries"][0]["lesson_number"] == 2
    assert detail.json()["edit_revision"] == 1

    deleted = await own.client.delete(
        f"/api/v1/scheduler/schedule/{own.entry.id}"
    )
    assert deleted.status_code == 200
    detail = await spaces.second.client.get(
        f"/api/v1/scheduler/publications/{publication['id']}"
    )
    assert detail.json()["entries"] == []
    assert detail.json()["edit_revision"] == 2

    archived = await own.client.post(f"/api/v1/scheduler/tasks/{own.task.id}/archive")
    assert archived.status_code == 200
    assert (
        await spaces.second.client.get("/api/v1/scheduler/publications")
    ).json() == []


@pytest.mark.asyncio
async def test_import_files_and_reference_names_are_personal(
    spaces, monkeypatch, tmp_path
):
    monkeypatch.setattr(scheduler, "UPLOAD_DIR", tmp_path)
    content = "Мероприятие,Группа,Преподаватель,Вид потока,Кол-во пар\nМатематика,A [20],Same teacher,Л,1\n".encode()
    for own in [spaces.first, spaces.second]:
        response = await own.client.post(
            "/api/v1/scheduler/import/streams",
            files={"file": ("same.csv", content, "text/csv")},
        )
        assert response.status_code == 200, response.text
        own.imported_id = response.json()["batch_id"]
        assert len(list((tmp_path / str(own.user.id)).iterdir())) == 1
    response = await spaces.first.client.delete(
        f"/api/v1/scheduler/import/history/{spaces.second.imported_id}"
    )
    assert response.status_code == 404
    assert len(list((tmp_path / str(spaces.second.user.id)).iterdir())) == 1


@pytest.mark.asyncio
async def test_unbound_sessions_fail_closed_and_foreign_keys_are_checked(spaces):
    async with spaces.factory() as db:
        assert await db.get(Teacher, spaces.first.teacher.id) is None
        db.add(Teacher(name="Unowned"))
        with pytest.raises(WorkspaceAccessError):
            await db.flush()
        await db.rollback()
    async with spaces.factory() as db:
        bind_workspace(db, spaces.first.user.id)
        assert await db.get(Teacher, spaces.second.teacher.id) is None
        db.add(
            Teacher(name="Illegal reference", department_id=spaces.second.department.id)
        )
        with pytest.raises(WorkspaceAccessError):
            await db.flush()
        await db.rollback()
        with pytest.raises(WorkspaceAccessError):
            bind_workspace(db, spaces.second.user.id)


@pytest.mark.asyncio
async def test_worker_resolves_task_owner_and_never_reads_other_streams(
    spaces, monkeypatch
):
    import services.scalable_generation_service as module

    monkeypatch.setattr(module, "sessionmaker", spaces.factory)
    own = spaces.second
    async with spaces.factory() as db:
        bind_workspace(db, own.user.id)
        task = GenerationTask(status="queued", groups_json='["A"]', settings_json="{}")
        db.add(task)
        await db.commit()
        task_id = task.id
    payload = await ScalableGenerationService.prepare(
        task_id, ["A"], [], ["Лекция"], "2026-09-07", "2026-09-07", None
    )
    assert payload is not None
    async with spaces.factory() as db:
        await bind_task_workspace(db, task_id)
        assert db.info["workspace_owner_id"] == own.user.id
        assert list((await db.scalars(select(Stream.id))).all()) == [own.stream.id]
        components = list(
            (
                await db.scalars(
                    select(GenerationComponent).where(
                        GenerationComponent.task_id == task_id
                    )
                )
            ).all()
        )
        assert components
        assert all(item.owner_id == own.user.id for item in components)
    async with spaces.factory() as db:
        await bind_task_workspace(db, 999999)
        assert await db.scalar(select(func.count(Stream.id))) == 0


def test_legacy_upload_cleanup_preserves_personal_files(tmp_path):
    from services.upload_service import purge_legacy_uploads

    (tmp_path / "old.xlsx").write_bytes(b"old")
    (tmp_path / "old.csv").write_bytes(b"old")
    (tmp_path / ".gitkeep").write_bytes(b"")
    personal = tmp_path / "1"
    personal.mkdir()
    (personal / "new.xlsx").write_bytes(b"private")
    assert purge_legacy_uploads(tmp_path) == 2
    assert purge_legacy_uploads(tmp_path) == 0
    assert (personal / "new.xlsx").read_bytes() == b"private"
    assert (tmp_path / ".gitkeep").exists()
