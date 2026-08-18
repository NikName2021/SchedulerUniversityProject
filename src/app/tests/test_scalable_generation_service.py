import datetime
import json
from types import SimpleNamespace

import pytest
import services.scalable_generation_service as scalable_module
from core.config import MAX_LESSON_NUMBER
from database import (
    FileType,
    GenerationTask,
    ImportBatch,
    ScheduleEntry,
    Stream,
    StreamGroup,
    Teacher,
    WeeklyLessonDemand,
)
from schemas.planning import AcademicPeriodCreate
from services.planning_service import PlanningService
from services.scalable_generation_service import (
    ScalableGenerationService,
    _teacher_unavailable,
)
from services.scalable_scheduler import solve_event_component
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker


def test_whitelist_specific_date_remains_available() -> None:
    stream = SimpleNamespace(
        teacher=SimpleNamespace(
            restrictions_json=json.dumps(
                {
                    "mode": "whitelist",
                    "recurring": [],
                    "specific": ["2026-09-07-2"],
                }
            )
        )
    )

    unavailable = _teacher_unavailable(stream, "2026-09-07", "2026-09-07")

    assert ["2026-09-07", 1] in unavailable
    assert ["2026-09-07", 2] not in unavailable


@pytest.mark.asyncio
async def test_scalable_pipeline_saves_parallel_components(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_sessionmaker = sessionmaker(
        db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    monkeypatch.setattr(scalable_module, "sessionmaker", test_sessionmaker)

    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Тестовая неделя",
            starts_on=datetime.date(2026, 9, 7),
            ends_on=datetime.date(2026, 9, 7),
        ),
        db_session,
    )
    week = period.weeks[0]
    batch = ImportBatch(filename="streams.xlsx", file_type=FileType.STREAMS)
    teacher_one = Teacher(name="Иванов И.И.")
    teacher_two = Teacher(name="Петров П.П.")
    db_session.add_all([batch, teacher_one, teacher_two])
    await db_session.flush()

    lecture = Stream(
        import_batch_id=batch.id,
        teacher_id=teacher_one.id,
        event_name="Математика",
        stream_type="Лекция",
        lessons_count=1,
    )
    seminar = Stream(
        import_batch_id=batch.id,
        teacher_id=teacher_two.id,
        event_name="Физика",
        stream_type="Семинар",
        lessons_count=1,
    )
    db_session.add_all([lecture, seminar])
    await db_session.flush()
    db_session.add_all(
        [
            StreamGroup(stream_id=lecture.id, group_name="A", group_size=20),
            StreamGroup(stream_id=lecture.id, group_name="B", group_size=20),
            StreamGroup(stream_id=seminar.id, group_name="C", group_size=15),
            WeeklyLessonDemand(
                week_id=week.id, stream_id=lecture.id, lessons_count=1, priority=5
            ),
            WeeklyLessonDemand(
                week_id=week.id, stream_id=seminar.id, lessons_count=1, priority=5
            ),
        ]
    )
    task = GenerationTask(
        planning_week_id=week.id,
        groups_json=json.dumps(["A", "B", "C"]),
        holidays_json="[]",
        settings_json="{}",
        start_date=datetime.datetime(2026, 9, 7),
        end_date=datetime.datetime(2026, 9, 7),
        status="queued",
    )
    db_session.add(task)
    await db_session.commit()

    class DateAfterPlanningPeriod(datetime.date):
        @classmethod
        def today(cls) -> "DateAfterPlanningPeriod":
            return cls(2027, 1, 1)

    monkeypatch.setattr(scalable_module, "date", DateAfterPlanningPeriod)

    payload = await ScalableGenerationService.prepare(
        task.id,
        ["A", "B", "C"],
        [],
        ["Лекция", "Семинар"],
        "2026-09-07",
        "2026-09-07",
        week.id,
    )

    assert payload is not None
    assert payload["context"]["lessons"][-1] == MAX_LESSON_NUMBER == 6
    assert payload["context"]["immutable_before"] == "2026-09-07"
    monkeypatch.setattr(scalable_module, "date", datetime.date)
    assert len(payload["components"]) == 2
    results = []
    for component in payload["components"]:
        result = solve_event_component(component["events"], payload["context"])
        results.append(result)
        await ScalableGenerationService.record_component_result(
            task.id, component["component_id"], result
        )

    assert await ScalableGenerationService.finalize(
        task.id, results, payload["context"]
    )
    async with test_sessionmaker() as verification_session:
        entries = list(
            (
                await verification_session.execute(
                    select(ScheduleEntry).where(ScheduleEntry.task_id == task.id)
                )
            ).scalars()
        )
        refreshed_task = await verification_session.get(GenerationTask, task.id)

    assert len(entries) == 3
    assert {entry.group_name for entry in entries} == {"A", "B", "C"}
    assert all(entry.room_id is None for entry in entries)
    assert all(entry.room_ref_id is None for entry in entries)
    assert refreshed_task is not None
    assert refreshed_task.status == "success"
    assert refreshed_task.progress_percent == 100

    incremental_task = GenerationTask(
        planning_week_id=week.id,
        groups_json=json.dumps(["A", "B", "C"]),
        holidays_json="[]",
        settings_json=json.dumps(
            {
                "base_task_id": task.id,
                "affected_stream_ids": [seminar.id],
            }
        ),
        start_date=datetime.datetime(2026, 9, 7),
        end_date=datetime.datetime(2026, 9, 7),
        status="queued",
    )
    async with test_sessionmaker() as setup_session:
        setup_session.add(incremental_task)
        await setup_session.commit()
        incremental_task_id = incremental_task.id

    incremental_payload = await ScalableGenerationService.prepare(
        incremental_task_id,
        ["A", "B", "C"],
        [],
        ["Лекция", "Семинар"],
        "2026-09-07",
        "2026-09-07",
        week.id,
    )
    assert incremental_payload is not None
    assert len(incremental_payload["components"]) == 1
    assert len(incremental_payload["context"]["carry_over_entries"]) == 2

    incremental_results = [
        solve_event_component(
            incremental_payload["components"][0]["events"],
            incremental_payload["context"],
        )
    ]
    assert await ScalableGenerationService.finalize(
        incremental_task_id,
        incremental_results,
        incremental_payload["context"],
    )
    async with test_sessionmaker() as verification_session:
        incremental_entries = list(
            (
                await verification_session.execute(
                    select(ScheduleEntry).where(
                        ScheduleEntry.task_id == incremental_task_id
                    )
                )
            ).scalars()
        )

    assert len(incremental_entries) == 3
    assert {entry.source_stream_id for entry in incremental_entries} == {
        lecture.id,
        seminar.id,
    }
