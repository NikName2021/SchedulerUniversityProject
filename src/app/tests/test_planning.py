import datetime

import pytest
from database import (
    AvailabilityRule,
    FileType,
    GenerationTask,
    ImportBatch,
    ScheduleEntry,
    Stream,
    StreamGroup,
    StudentGroup,
    Teacher,
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
async def test_semester_demand_is_distributed_once_across_weeks(db_session) -> None:
    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Осенний семестр",
            starts_on=datetime.date(2026, 9, 7),
            ends_on=datetime.date(2026, 10, 4),
        ),
        db_session,
    )
    batch = ImportBatch(filename="streams.xlsx", file_type=FileType.STREAMS)
    teacher = Teacher(name="Иванов И.И.")
    db_session.add_all([batch, teacher])
    await db_session.flush()
    stream = Stream(
        import_batch_id=batch.id,
        teacher_id=teacher.id,
        event_name="Математика",
        stream_type="Лекция",
        lessons_count=10,
    )
    db_session.add(stream)
    await db_session.flush()
    db_session.add(
        StreamGroup(stream_id=stream.id, group_name="МАТ-101", group_size=25)
    )
    await db_session.commit()

    summary = await PlanningService.distribute_semester_demands(
        period.id, ["МАТ-101"], ["Лекция"], set(), db_session
    )

    assert summary.planned_lessons == 10
    assert summary.distributed_lessons == 10
    assert [week.lessons_count for week in summary.weeks] == [3, 3, 2, 2]
    result = await db_session.execute(
        select(WeeklyLessonDemand).order_by(WeeklyLessonDemand.week_id)
    )
    assert sum(demand.lessons_count for demand in result.scalars()) == 10

    repeated = await PlanningService.distribute_semester_demands(
        period.id, ["МАТ-101"], ["Лекция"], set(), db_session
    )
    repeated_rows = await db_session.execute(select(WeeklyLessonDemand))
    assert repeated.distributed_lessons == 10
    assert len(repeated_rows.scalars().all()) == len(period.weeks)


@pytest.mark.asyncio
async def test_semester_demand_balances_short_streams_across_weeks(
    db_session,
) -> None:
    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Осенний семестр",
            starts_on=datetime.date(2026, 9, 7),
            ends_on=datetime.date(2026, 10, 4),
        ),
        db_session,
    )
    batch = ImportBatch(filename="streams.xlsx", file_type=FileType.STREAMS)
    db_session.add(batch)
    await db_session.flush()

    for index in range(12):
        stream = Stream(
            import_batch_id=batch.id,
            event_name=f"Дисциплина {index + 1}",
            stream_type="Семинар",
            lessons_count=1,
        )
        db_session.add(stream)
        await db_session.flush()
        db_session.add(
            StreamGroup(stream_id=stream.id, group_name="МАТ-101", group_size=25)
        )
    await db_session.commit()

    summary = await PlanningService.distribute_semester_demands(
        period.id, ["МАТ-101"], ["Семинар"], set(), db_session
    )

    assert [week.lessons_count for week in summary.weeks] == [3, 3, 3, 3]


@pytest.mark.asyncio
async def test_visiting_teacher_load_uses_only_available_weeks(db_session) -> None:
    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Осенний семестр",
            starts_on=datetime.date(2026, 9, 7),
            ends_on=datetime.date(2026, 10, 4),
        ),
        db_session,
    )
    batch = ImportBatch(filename="streams.xlsx", file_type=FileType.STREAMS)
    teacher = Teacher(name="Выездной преподаватель")
    db_session.add_all([batch, teacher])
    await db_session.flush()
    stream = Stream(
        import_batch_id=batch.id,
        teacher_id=teacher.id,
        event_name="Интенсив",
        stream_type="Семинар",
        lessons_count=8,
    )
    db_session.add(stream)
    await db_session.flush()
    db_session.add_all(
        [
            StreamGroup(stream_id=stream.id, group_name="ИНТ-101", group_size=20),
            AvailabilityRule(
                teacher_id=teacher.id,
                rule_kind="available",
                recurrence="date_range",
                starts_on=period.weeks[1].starts_on,
                ends_on=period.weeks[2].ends_on,
                lesson_start=1,
                lesson_end=7,
                is_hard=True,
            ),
        ]
    )
    await db_session.commit()

    summary = await PlanningService.distribute_semester_demands(
        period.id, ["ИНТ-101"], ["Семинар"], set(), db_session
    )

    assert [week.lessons_count for week in summary.weeks] == [0, 4, 4, 0]


@pytest.mark.asyncio
async def test_visiting_teacher_availability_overrides_week_load_balance(
    db_session,
) -> None:
    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Осенний семестр",
            starts_on=datetime.date(2026, 9, 7),
            ends_on=datetime.date(2026, 10, 4),
        ),
        db_session,
    )
    batch = ImportBatch(filename="streams.xlsx", file_type=FileType.STREAMS)
    visiting_teacher = Teacher(name="Приезжий преподаватель")
    db_session.add_all([batch, visiting_teacher])
    await db_session.flush()

    visiting_stream = Stream(
        import_batch_id=batch.id,
        teacher_id=visiting_teacher.id,
        event_name="Выездной интенсив",
        stream_type="Семинар",
        lessons_count=6,
    )
    db_session.add(visiting_stream)
    await db_session.flush()
    db_session.add(
        StreamGroup(
            stream_id=visiting_stream.id,
            group_name="ИНТ-101",
            group_size=20,
        )
    )

    available_date = period.weeks[2].starts_on
    db_session.add_all(
        [
            AvailabilityRule(
                teacher_id=visiting_teacher.id,
                rule_kind="available",
                recurrence="specific",
                specific_date=available_date,
                lesson_start=lesson,
                lesson_end=lesson,
                is_hard=True,
            )
            for lesson in range(1, 7)
        ]
    )

    for index in range(12):
        stream = Stream(
            import_batch_id=batch.id,
            event_name=f"Обычная дисциплина {index + 1}",
            stream_type="Семинар",
            lessons_count=1,
        )
        db_session.add(stream)
        await db_session.flush()
        db_session.add(
            StreamGroup(stream_id=stream.id, group_name="ИНТ-101", group_size=20)
        )
    await db_session.commit()

    summary = await PlanningService.distribute_semester_demands(
        period.id, ["ИНТ-101"], ["Семинар"], set(), db_session
    )

    demands_result = await db_session.execute(
        select(WeeklyLessonDemand).where(
            WeeklyLessonDemand.stream_id == visiting_stream.id
        )
    )
    visiting_demands = {
        demand.week_id: demand.lessons_count for demand in demands_result.scalars()
    }

    assert [
        visiting_demands[week.id] for week in period.weeks
    ] == [0, 0, 6, 0]
    assert [week.lessons_count for week in summary.weeks] == [4, 4, 6, 4]


@pytest.mark.asyncio
async def test_distribution_rejects_teacher_capacity_shortage(db_session) -> None:
    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Короткий модуль",
            starts_on=datetime.date(2026, 9, 7),
            ends_on=datetime.date(2026, 9, 13),
        ),
        db_session,
    )
    batch = ImportBatch(filename="streams.xlsx", file_type=FileType.STREAMS)
    teacher = Teacher(name="Занятый преподаватель")
    db_session.add_all([batch, teacher])
    await db_session.flush()
    stream = Stream(
        import_batch_id=batch.id,
        teacher_id=teacher.id,
        event_name="Дефицит",
        stream_type="Лекция",
        lessons_count=2,
    )
    db_session.add(stream)
    await db_session.flush()
    db_session.add_all(
        [
            StreamGroup(stream_id=stream.id, group_name="ДЕФ-101", group_size=20),
            AvailabilityRule(
                teacher_id=teacher.id,
                rule_kind="available",
                recurrence="specific",
                specific_date=datetime.date(2026, 9, 7),
                lesson_start=1,
                lesson_end=1,
                is_hard=True,
            ),
        ]
    )
    await db_session.commit()

    with pytest.raises(ValueError, match="не помещается 1 пар"):
        await PlanningService.distribute_semester_demands(
            period.id, ["ДЕФ-101"], ["Лекция"], set(), db_session
        )

    result = await db_session.execute(select(WeeklyLessonDemand))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_distribution_counts_published_shared_lesson_once(db_session) -> None:
    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Две недели",
            starts_on=datetime.date(2026, 9, 7),
            ends_on=datetime.date(2026, 9, 20),
        ),
        db_session,
    )
    batch = ImportBatch(filename="streams.xlsx", file_type=FileType.STREAMS)
    teacher = Teacher(name="Лектор")
    db_session.add_all([batch, teacher])
    await db_session.flush()
    stream = Stream(
        import_batch_id=batch.id,
        teacher_id=teacher.id,
        event_name="Общая лекция",
        stream_type="Лекция",
        lessons_count=4,
    )
    db_session.add(stream)
    await db_session.flush()
    db_session.add_all(
        [
            StreamGroup(stream_id=stream.id, group_name="ГР-1", group_size=20),
            StreamGroup(stream_id=stream.id, group_name="ГР-2", group_size=20),
        ]
    )
    task = GenerationTask(
        planning_week_id=period.weeks[0].id,
        publication_status="published",
        status="success",
    )
    db_session.add(task)
    await db_session.flush()
    for lesson in (1, 2):
        for group_name in ("ГР-1", "ГР-2"):
            db_session.add(
                ScheduleEntry(
                    task_id=task.id,
                    planning_week_id=period.weeks[0].id,
                    source_stream_id=stream.id,
                    group_name=group_name,
                    event_name=stream.event_name,
                    stream_type=stream.stream_type,
                    teacher_id=teacher.id,
                    date=datetime.datetime(2026, 9, 7, 8, 30),
                    lesson_number=lesson,
                )
            )
    await db_session.commit()

    summary = await PlanningService.distribute_semester_demands(
        period.id, ["ГР-1", "ГР-2"], ["Лекция"], set(), db_session
    )

    assert summary.published_lessons == 2
    assert summary.distributed_lessons == 4
    assert [week.lessons_count for week in summary.weeks] == [2, 2]


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
