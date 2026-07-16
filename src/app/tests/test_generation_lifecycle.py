import datetime

import pytest
from database import GenerationIssue, GenerationTask, ScheduleEntry, Teacher
from services.generation_lifecycle_service import GenerationLifecycleService
from services.schedule_service import ScheduleService
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
