import datetime

import pytest
from database import (
    AcademicPeriod,
    FileType,
    GenerationComponent,
    GenerationIssue,
    GenerationLock,
    GenerationTask,
    ImportBatch,
    PlanningWeek,
    ScheduleEntry,
    Stream,
    StreamGroup,
    Teacher,
)
from httpx import AsyncClient
from services.generation_lifecycle_service import GenerationLifecycleService
from services.schedule_service import ScheduleService
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_generation_lock_and_version_lifecycle(db_session: AsyncSession) -> None:
    starts_on = datetime.datetime(2026, 9, 7)
    ends_on = datetime.datetime(2026, 9, 13)
    first = await GenerationLifecycleService.reserve_task(
        db_session,
        groups=["ИВТ-101"],
        holidays=[],
        settings={},
        planning_week_id=None,
        start_date=starts_on,
        end_date=ends_on,
    )

    with pytest.raises(RuntimeError, match="already running"):
        await GenerationLifecycleService.reserve_task(
            db_session,
            groups=["ИВТ-101"],
            holidays=[],
            settings={},
            planning_week_id=None,
            start_date=starts_on,
            end_date=ends_on,
        )

    first.status = "success"
    await GenerationLifecycleService.release_locks(first.id, db_session)
    await db_session.commit()
    await GenerationLifecycleService.publish(first, db_session)

    second = await GenerationLifecycleService.reserve_task(
        db_session,
        groups=["ИВТ-101"],
        holidays=[],
        settings={},
        planning_week_id=None,
        start_date=starts_on,
        end_date=ends_on,
        parent_task_id=first.id,
    )
    second.status = "partial"
    await GenerationLifecycleService.release_locks(second.id, db_session)
    await db_session.commit()
    await GenerationLifecycleService.publish(second, db_session)
    await db_session.refresh(first)

    assert second.version_number == first.version_number + 1
    assert second.publication_status == "published"
    assert first.publication_status == "archived"


@pytest.mark.asyncio
async def test_completed_generation_task_can_be_deleted(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    task = GenerationTask(
        groups_json='["A"]',
        holidays_json="[]",
        settings_json="{}",
        status="success",
    )
    db_session.add(task)
    await db_session.flush()
    child = GenerationTask(
        parent_task_id=task.id,
        groups_json='["A"]',
        holidays_json="[]",
        settings_json="{}",
        status="failed",
    )
    db_session.add_all(
        [
            child,
            GenerationLock(scope_key="test-delete", task_id=task.id),
            GenerationIssue(
                task_id=task.id,
                kind="unassigned",
                message="Не размещено занятие",
            ),
            GenerationComponent(
                task_id=task.id,
                component_key="component-0001",
            ),
            ScheduleEntry(
                task_id=task.id,
                group_name="A",
                event_name="Математика",
                stream_type="Лекция",
            ),
        ]
    )
    await db_session.commit()

    response = await api_client.delete(f"/api/v1/scheduler/tasks/{task.id}")

    assert response.status_code == 204
    for model in (
        GenerationTask,
        GenerationLock,
        GenerationIssue,
        GenerationComponent,
        ScheduleEntry,
    ):
        remaining = await db_session.scalar(
            select(func.count()).select_from(model).where(
                model.id == task.id
                if model is GenerationTask
                else model.task_id == task.id
            )
        )
        assert remaining == 0
    await db_session.refresh(child)
    assert child.parent_task_id is None


@pytest.mark.asyncio
async def test_semester_batch_can_be_deleted(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    batch_id = "semester-delete-2026"
    tasks = [
        GenerationTask(
            semester_batch_id=batch_id,
            groups_json='["A"]',
            holidays_json="[]",
            settings_json="{}",
            status="success",
        )
        for _ in range(2)
    ]
    db_session.add_all(tasks)
    await db_session.commit()

    response = await api_client.delete(
        f"/api/v1/scheduler/semester-batches/{batch_id}"
    )

    assert response.status_code == 204
    remaining = await db_session.scalar(
        select(func.count())
        .select_from(GenerationTask)
        .where(GenerationTask.semester_batch_id == batch_id)
    )
    assert remaining == 0


@pytest.mark.asyncio
async def test_groups_endpoint_only_returns_scheduled_groups_for_calculation(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    batch_id = "semester-groups-2026"
    first_task = GenerationTask(
        semester_batch_id=batch_id,
        groups_json='["A", "B", "C"]',
        holidays_json="[]",
        settings_json="{}",
        status="success",
    )
    second_task = GenerationTask(
        semester_batch_id=batch_id,
        groups_json='["D"]',
        holidays_json="[]",
        settings_json="{}",
        status="success",
    )
    unrelated_task = GenerationTask(
        groups_json='["OTHER"]',
        holidays_json="[]",
        settings_json="{}",
        status="success",
    )
    db_session.add_all([first_task, second_task, unrelated_task])
    await db_session.flush()
    scheduled_on = datetime.datetime(2026, 9, 7)
    db_session.add_all(
        [
            ScheduleEntry(
                task_id=first_task.id,
                group_name="A",
                event_name="Математика",
                stream_type="Лекция",
                date=scheduled_on,
                lesson_number=1,
            ),
            ScheduleEntry(
                task_id=first_task.id,
                group_name="B",
                event_name="Физика",
                stream_type="Семинар",
            ),
            ScheduleEntry(
                task_id=first_task.id,
                group_name="A, C (L1)",
                event_name="Английский язык",
                stream_type="Семинар",
                date=scheduled_on,
                lesson_number=2,
            ),
            ScheduleEntry(
                task_id=second_task.id,
                group_name="D",
                event_name="Информатика",
                stream_type="Семинар",
                date=scheduled_on,
                lesson_number=2,
            ),
            ScheduleEntry(
                task_id=unrelated_task.id,
                group_name="OTHER",
                event_name="История",
                stream_type="Лекция",
                date=scheduled_on,
                lesson_number=3,
            ),
        ]
    )
    await db_session.commit()

    task_response = await api_client.get(
        f"/api/v1/scheduler/groups?task_id={first_task.id}"
    )
    semester_response = await api_client.get(
        f"/api/v1/scheduler/groups?semester_batch_id={batch_id}"
    )
    subgroup_schedule_response = await api_client.get(
        f"/api/v1/scheduler/schedule?task_id={first_task.id}&group_name=C"
    )

    assert task_response.status_code == 200
    assert task_response.json() == {"groups": ["A", "C"]}
    assert semester_response.status_code == 200
    assert semester_response.json() == {"groups": ["A", "C", "D"]}
    assert subgroup_schedule_response.status_code == 200
    assert [item["event_name"] for item in subgroup_schedule_response.json()] == [
        "Английский язык"
    ]


@pytest.mark.asyncio
async def test_experimental_group_preview_returns_related_streams(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    batch = ImportBatch(filename="groups.xlsx", file_type=FileType.STREAMS)
    db_session.add(batch)
    await db_session.flush()
    labels = [
        "К0109-23",
        "К0609-23",
        "К0109-23, К0609-23",
        "К0109-23, К0609-23 (L1)",
        "К0109-23, К0609-23 (L2)",
        "К0209-23",
    ]
    streams = [
        Stream(
            import_batch_id=batch.id,
            event_name=f"Событие {index}",
            stream_type="Семинар",
        )
        for index, _label in enumerate(labels)
    ]
    db_session.add_all(streams)
    await db_session.flush()
    db_session.add_all(
        [
            StreamGroup(
                stream_id=stream.id,
                group_name=label,
                group_size=0,
            )
            for stream, label in zip(streams, labels)
        ]
    )
    await db_session.commit()

    response = await api_client.post(
        "/api/v1/scheduler/groups/selection-preview",
        json={"groups": ["К0109-23"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["base_groups"] == ["К0109-23", "К0609-23"]
    assert payload["joint_groups"] == ["К0109-23, К0609-23"]
    assert len(payload["subgroup_groups"]) == 2
    assert "К0209-23" not in payload["selected_groups"]


@pytest.mark.asyncio
async def test_schedule_entry_details_expose_joint_group_and_subgroup(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    task = GenerationTask(
        groups_json='["К0109-23"]',
        holidays_json="[]",
        settings_json="{}",
        status="success",
    )
    db_session.add(task)
    await db_session.flush()
    entry = ScheduleEntry(
        task_id=task.id,
        group_name="К0109-23, К0609-23 (L2)",
        event_name="Английский язык",
        stream_type="Семинар",
        date=datetime.datetime(2026, 9, 7),
        lesson_number=2,
    )
    db_session.add(entry)
    await db_session.commit()

    response = await api_client.get(
        f"/api/v1/scheduler/schedule/{entry.id}/details"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["base_groups"] == ["К0109-23", "К0609-23"]
    assert payload["subgroups"] == ["L2"]
    assert payload["audience_label"] == "К0109-23, К0609-23 (L2)"


@pytest.mark.asyncio
async def test_manual_entry_can_move_to_another_semester_week(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    period = AcademicPeriod(
        name="Осенний семестр",
        starts_on=datetime.date(2026, 9, 7),
        ends_on=datetime.date(2026, 9, 20),
    )
    first_week = PlanningWeek(
        period=period,
        sequence_number=1,
        starts_on=datetime.date(2026, 9, 7),
        ends_on=datetime.date(2026, 9, 13),
    )
    second_week = PlanningWeek(
        period=period,
        sequence_number=2,
        starts_on=datetime.date(2026, 9, 14),
        ends_on=datetime.date(2026, 9, 20),
    )
    db_session.add(period)
    await db_session.flush()
    batch_id = "semester-manual-move"
    first_task = GenerationTask(
        planning_week_id=first_week.id,
        semester_batch_id=batch_id,
        groups_json='["A"]',
        holidays_json="[]",
        settings_json="{}",
        status="success",
        start_date=datetime.datetime(2026, 9, 7),
        end_date=datetime.datetime(2026, 9, 13),
    )
    second_task = GenerationTask(
        planning_week_id=second_week.id,
        semester_batch_id=batch_id,
        groups_json='["A"]',
        holidays_json="[]",
        settings_json="{}",
        status="success",
        start_date=datetime.datetime(2026, 9, 14),
        end_date=datetime.datetime(2026, 9, 20),
    )
    db_session.add_all([first_task, second_task])
    await db_session.flush()
    entry = ScheduleEntry(
        task_id=first_task.id,
        planning_week_id=first_week.id,
        group_name="A",
        event_name="Математика",
        stream_type="Семинар",
    )
    db_session.add(entry)
    await db_session.commit()

    response = await api_client.patch(
        f"/api/v1/scheduler/schedule/{entry.id}",
        json={"date": "2026-09-14", "lesson_number": 1},
    )

    assert response.status_code == 200
    await db_session.refresh(entry)
    assert entry.task_id == second_task.id
    assert entry.planning_week_id == second_week.id
    assert entry.date == datetime.datetime(2026, 9, 14)
    assert any(item["id"] == entry.id for item in response.json()["entries"])


@pytest.mark.asyncio
async def test_manual_lunch_violation_is_saved_with_warning(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    task = GenerationTask(
        groups_json='["A"]',
        holidays_json="[]",
        settings_json="{}",
        status="success",
    )
    db_session.add(task)
    await db_session.flush()
    scheduled_on = datetime.datetime(2026, 9, 7)
    third = ScheduleEntry(
        task_id=task.id,
        group_name="A",
        event_name="Математика",
        stream_type="Лекция",
        date=scheduled_on,
        lesson_number=3,
    )
    moved = ScheduleEntry(
        task_id=task.id,
        group_name="A",
        event_name="Физика",
        stream_type="Семинар",
        date=scheduled_on,
        lesson_number=5,
    )
    db_session.add_all([third, moved])
    await db_session.commit()

    response = await api_client.patch(
        f"/api/v1/scheduler/schedule/{moved.id}",
        json={"date": "2026-09-07", "lesson_number": 4},
    )

    assert response.status_code == 200
    await db_session.refresh(moved)
    assert moved.lesson_number == 4
    warnings = {
        item["id"]: item["warning"] for item in response.json()["entries"]
    }
    assert "нет свободного окна для обеда" in warnings[third.id]
    assert "нет свободного окна для обеда" in warnings[moved.id]


@pytest.mark.asyncio
async def test_semester_tasks_keep_a_shared_batch_identifier(
    db_session: AsyncSession,
) -> None:
    batch_id = "semester-run-2026-09"
    period = AcademicPeriod(
        name="Осенний семестр",
        starts_on=datetime.date(2026, 9, 1),
        ends_on=datetime.date(2026, 12, 31),
    )
    week = PlanningWeek(
        period=period,
        sequence_number=1,
        starts_on=datetime.date(2026, 9, 7),
        ends_on=datetime.date(2026, 9, 13),
    )
    db_session.add(period)
    await db_session.flush()
    task = await GenerationLifecycleService.reserve_task(
        db_session,
        groups=["ИВТ-101"],
        holidays=[],
        settings={"semester_period_id": period.id},
        planning_week_id=week.id,
        start_date=datetime.datetime(2026, 9, 7),
        end_date=datetime.datetime(2026, 9, 13),
        semester_batch_id=batch_id,
    )

    assert task.semester_batch_id == batch_id


@pytest.mark.asyncio
async def test_manual_change_detects_teacher_conflict_and_diagnostics(
    db_session: AsyncSession,
) -> None:
    teacher = Teacher(name="Иванов И.И.")
    task = GenerationTask(
        groups_json='["A", "B"]',
        holidays_json="[]",
        settings_json="{}",
        status="success",
    )
    db_session.add_all([teacher, task])
    await db_session.flush()
    slot = datetime.datetime(2026, 9, 7)
    first = ScheduleEntry(
        task_id=task.id,
        group_name="A",
        event_name="Математика",
        stream_type="Семинар",
        teacher_id=teacher.id,
        date=slot,
        lesson_number=1,
    )
    second = ScheduleEntry(
        task_id=task.id,
        group_name="B",
        event_name="Физика",
        stream_type="Семинар",
        teacher_id=teacher.id,
        date=slot,
        lesson_number=1,
    )
    issue = GenerationIssue(
        task_id=task.id,
        kind="unassigned",
        severity="error",
        message="Не размещено занятие",
        group_name="A",
    )
    db_session.add_all([first, second, issue])
    await db_session.commit()

    conflicts = await ScheduleService.validate_manual_changes(
        task.id, {second.id}, db_session
    )
    diagnostics = await GenerationLifecycleService.diagnostics(task.id, db_session)

    assert any("Преподаватель уже занят" in item for item in conflicts)
    assert diagnostics["counts"] == {"unassigned": 1}
    assert diagnostics["issues"][0]["group_name"] == "A"


@pytest.mark.asyncio
async def test_worker_loss_marks_active_task_failed_and_releases_lock(
    db_session: AsyncSession,
) -> None:
    task = await GenerationLifecycleService.reserve_task(
        db_session,
        groups=["A"],
        holidays=[],
        settings={},
        planning_week_id=None,
        start_date=datetime.datetime(2026, 9, 7),
        end_date=datetime.datetime(2026, 9, 13),
    )
    task.status = "running"
    await db_session.commit()

    await GenerationLifecycleService.fail_active_task(
        task.id, "Worker lost", db_session
    )
    retry = await GenerationLifecycleService.reserve_task(
        db_session,
        groups=["A"],
        holidays=[],
        settings={},
        planning_week_id=None,
        start_date=datetime.datetime(2026, 9, 7),
        end_date=datetime.datetime(2026, 9, 13),
        parent_task_id=task.id,
    )

    await db_session.refresh(task)
    assert task.status == "failed"
    assert task.progress_percent == 100
    assert retry.id != task.id
