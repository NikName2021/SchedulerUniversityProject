import datetime

import pandas as pd
import pytest
from database import (
    AvailabilityRule,
    FileType,
    GenerationTask,
    ImportBatch,
    ScheduleEntry,
    Stream,
    Teacher,
)
from services.schedule_service import ScheduleService
from sqlalchemy import select


@pytest.mark.asyncio
async def test_teacher_availability_import_updates_structured_rules(
    db_session,
) -> None:
    teacher = Teacher(name="Иванов И.И.")
    db_session.add(teacher)
    await db_session.commit()
    dataframe = pd.DataFrame(
        [
            {
                "ФИО преподавателя": teacher.name,
                "Режим": "blacklist",
                "Регулярные окна (День_Пара)": "1-2",
                "Конкретные даты (ГГГГ-ММ-ДД_Пара)": "2026-09-08-3",
            }
        ]
    )

    updated = await ScheduleService.import_teacher_availability(
        dataframe, db_session
    )
    await db_session.commit()

    rules = list((await db_session.execute(select(AvailabilityRule))).scalars())
    assert updated == 1
    assert {(rule.recurrence, rule.lesson_start) for rule in rules} == {
        ("weekly", 2),
        ("specific", 3),
    }


@pytest.mark.asyncio
async def test_warning_refresh_detects_room_conflicts_without_flagging_shared_stream(
    db_session,
) -> None:
    task = GenerationTask(status="success")
    batch = ImportBatch(filename="streams.xlsx", file_type=FileType.STREAMS)
    db_session.add_all([task, batch])
    await db_session.flush()
    streams = [
        Stream(import_batch_id=batch.id, event_name=f"Поток {index}")
        for index in range(1, 4)
    ]
    db_session.add_all(streams)
    await db_session.flush()
    slot = datetime.datetime(2026, 9, 7)
    conflicting_entries = [
        ScheduleEntry(
            task_id=task.id,
            source_stream_id=streams[0].id,
            group_name="А",
            event_name="Математика",
            stream_type="Семинар",
            room_id="101",
            date=slot,
            lesson_number=1,
        ),
        ScheduleEntry(
            task_id=task.id,
            source_stream_id=streams[1].id,
            group_name="Б",
            event_name="Физика",
            stream_type="Семинар",
            room_id="101",
            date=slot,
            lesson_number=1,
        ),
        ScheduleEntry(
            task_id=task.id,
            source_stream_id=streams[2].id,
            group_name="В",
            event_name="Общая лекция",
            stream_type="Лекция",
            room_id="201",
            date=slot,
            lesson_number=2,
        ),
        ScheduleEntry(
            task_id=task.id,
            source_stream_id=streams[2].id,
            group_name="Г",
            event_name="Общая лекция",
            stream_type="Лекция",
            room_id="201",
            date=slot,
            lesson_number=2,
        ),
    ]
    db_session.add_all(conflicting_entries)
    await db_session.commit()

    await ScheduleService.refresh_task_warnings(task.id, db_session)

    assert "Аудитория занята" in (conflicting_entries[0].warning or "")
    assert "Аудитория занята" in (conflicting_entries[1].warning or "")
    assert conflicting_entries[2].warning is None
    assert conflicting_entries[3].warning is None
