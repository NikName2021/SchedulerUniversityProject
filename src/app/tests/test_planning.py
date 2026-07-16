import datetime

import pytest
from database import (
    FileType,
    ImportBatch,
    Stream,
    StreamGroup,
    StudentGroup,
    WeeklyLessonDemand,
)
from schemas.planning import AcademicPeriodCreate, WeeklyDemandItem
from services.planning_service import PlanningService
from services.schedule_service import ScheduleService
from sqlalchemy import select


@pytest.mark.asyncio
async def test_create_period_splits_calendar_weeks(db_session) -> None:
    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Осенний семестр",
            starts_on=datetime.date(2026, 9, 2),
            ends_on=datetime.date(2026, 9, 15),
        ),
        db_session,
    )

    assert [(week.starts_on, week.ends_on) for week in period.weeks] == [
        (datetime.date(2026, 9, 2), datetime.date(2026, 9, 6)),
        (datetime.date(2026, 9, 7), datetime.date(2026, 9, 13)),
        (datetime.date(2026, 9, 14), datetime.date(2026, 9, 15)),
    ]


@pytest.mark.asyncio
async def test_weekly_demands_are_independent(db_session) -> None:
    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Модуль 1",
            period_type="module",
            starts_on=datetime.date(2026, 9, 7),
            ends_on=datetime.date(2026, 9, 20),
        ),
        db_session,
    )
    batch = ImportBatch(filename="streams.xlsx", file_type=FileType.STREAMS)
    db_session.add(batch)
    await db_session.flush()
    stream = Stream(
        import_batch_id=batch.id,
        event_name="Математика",
        stream_type="Лекция",
        lessons_count=2,
    )
    db_session.add(stream)
    await db_session.commit()

    first_week, second_week = period.weeks
    await PlanningService.replace_weekly_demands(
        first_week.id,
        [WeeklyDemandItem(stream_id=stream.id, lessons_count=2)],
        db_session,
    )
    await PlanningService.replace_weekly_demands(
        second_week.id,
        [WeeklyDemandItem(stream_id=stream.id, lessons_count=0)],
        db_session,
    )

    result = await db_session.execute(
        select(WeeklyLessonDemand).order_by(WeeklyLessonDemand.week_id)
    )
    assert [demand.lessons_count for demand in result.scalars()] == [2, 0]


@pytest.mark.asyncio
async def test_stream_import_normalizes_student_groups(db_session) -> None:
    batch = ImportBatch(filename="streams.xlsx", file_type=FileType.STREAMS)
    db_session.add(batch)
    await db_session.flush()

    await ScheduleService.import_streams(
        [
            {
                "event": "Физика",
                "type": "Лекция",
                "teacher": None,
                "lessons_count": 1,
                "groups": [{"name": "ФИЗ-101", "size": 24}],
            }
        ],
        batch.id,
        db_session,
    )

    student_group = (await db_session.execute(select(StudentGroup))).scalar_one()
    stream_group = (await db_session.execute(select(StreamGroup))).scalar_one()
    assert student_group.name == "ФИЗ-101"
    assert student_group.student_count == 24
    assert stream_group.student_group_id == student_group.id
