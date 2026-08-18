from collections import defaultdict
from datetime import date, timedelta
from fractions import Fraction

from core.config import GENERATION_LESSONS
from core.constants import STUDY_DAYS
from database import (
    AcademicPeriod,
    GenerationTask,
    PlanningWeek,
    ScheduleEntry,
    Stream,
    StreamGroup,
    WeeklyLessonDemand,
)
from schemas.planning import (
    AcademicPeriodCreate,
    SemesterDemandDistributionResult,
    SemesterWeekDistribution,
    WeeklyDemandItem,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.availability_service import build_availability_context


class PlanningService:
    @staticmethod
    async def create_period(
        payload: AcademicPeriodCreate, db: AsyncSession
    ) -> AcademicPeriod:
        period = AcademicPeriod(
            name=payload.name,
            period_type=payload.period_type,
            education_level=payload.education_level,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
        )
        db.add(period)
        await db.flush()

        if payload.create_weeks:
            cursor = payload.starts_on
            sequence_number = 1
            while cursor <= payload.ends_on:
                calendar_week_end = cursor + timedelta(days=6 - cursor.weekday())
                week_end = min(calendar_week_end, payload.ends_on)
                db.add(
                    PlanningWeek(
                        period_id=period.id,
                        sequence_number=sequence_number,
                        starts_on=cursor,
                        ends_on=week_end,
                    )
                )
                cursor = week_end + timedelta(days=1)
                sequence_number += 1

        await db.commit()
        return await PlanningService.get_period(period.id, db)

    @staticmethod
    async def get_period(period_id: int, db: AsyncSession) -> AcademicPeriod | None:
        result = await db.execute(
            select(AcademicPeriod)
            .where(AcademicPeriod.id == period_id)
            .options(selectinload(AcademicPeriod.weeks))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_periods(db: AsyncSession) -> list[AcademicPeriod]:
        result = await db.execute(
            select(AcademicPeriod)
            .options(selectinload(AcademicPeriod.weeks))
            .order_by(AcademicPeriod.starts_on.desc())
        )
        return list(result.scalars().unique().all())

    @staticmethod
    async def replace_weekly_demands(
        week_id: int, demands: list[WeeklyDemandItem], db: AsyncSession
    ) -> int:
        stream_ids = {item.stream_id for item in demands}
        if len(stream_ids) != len(demands):
            raise ValueError("stream_id values must be unique")

        if stream_ids:
            result = await db.execute(
                select(Stream.id).where(Stream.id.in_(stream_ids))
            )
            existing_ids = set(result.scalars().all())
            missing = stream_ids - existing_ids
            if missing:
                raise LookupError(f"Unknown streams: {sorted(missing)}")

        await db.execute(
            delete(WeeklyLessonDemand).where(WeeklyLessonDemand.week_id == week_id)
        )
        db.add_all(
            [
                WeeklyLessonDemand(
                    week_id=week_id,
                    stream_id=item.stream_id,
                    lessons_count=item.lessons_count,
                    priority=item.priority,
                )
                for item in demands
            ]
        )
        await db.commit()
        return len(demands)

    @staticmethod
    async def clone_weekly_demands(
        week_id: int,
        db: AsyncSession,
        source_week_id: int | None = None,
        use_stream_defaults: bool = False,
    ) -> int:
        if source_week_id is not None:
            result = await db.execute(
                select(WeeklyLessonDemand).where(
                    WeeklyLessonDemand.week_id == source_week_id
                )
            )
            items = [
                WeeklyDemandItem(
                    stream_id=demand.stream_id,
                    lessons_count=demand.lessons_count,
                    priority=demand.priority,
                )
                for demand in result.scalars().all()
            ]
        elif use_stream_defaults:
            result = await db.execute(
                select(Stream).where(Stream.is_ignored.is_(False))
            )
            items = [
                WeeklyDemandItem(
                    stream_id=stream.id,
                    lessons_count=stream.lessons_count,
                )
                for stream in result.scalars().all()
            ]
        else:
            raise ValueError("source_week_id or use_stream_defaults is required")

        return await PlanningService.replace_weekly_demands(week_id, items, db)

    @staticmethod
    async def distribute_semester_demands(
        period_id: int,
        groups: list[str],
        enabled_types: list[str],
        holidays: set[date],
        db: AsyncSession,
    ) -> SemesterDemandDistributionResult:
        period = await PlanningService.get_period(period_id, db)
        if period is None:
            raise LookupError("Academic period not found")
        weeks = list(period.weeks)
        if not weeks:
            raise ValueError("Academic period has no planning weeks")

        stream_query = (
            select(Stream)
            .join(Stream.groups)
            .where(
                StreamGroup.group_name.in_(groups),
                Stream.is_ignored.is_(False),
            )
            .options(selectinload(Stream.groups), selectinload(Stream.teacher))
        )
        if enabled_types:
            stream_query = stream_query.where(Stream.stream_type.in_(enabled_types))
        stream_result = await db.execute(stream_query)
        streams = list(stream_result.scalars().unique())
        if not streams:
            raise ValueError("No active streams found for selected groups and types")

        week_ids = [week.id for week in weeks]
        stream_ids = [stream.id for stream in streams]
        existing_result = await db.execute(
            select(WeeklyLessonDemand).where(
                WeeklyLessonDemand.week_id.in_(week_ids),
                WeeklyLessonDemand.stream_id.in_(stream_ids),
            )
        )
        priorities: dict[int, int] = {}
        for demand in existing_result.scalars():
            priorities.setdefault(demand.stream_id, demand.priority)

        published_result = await db.execute(
            select(
                ScheduleEntry.source_stream_id,
                ScheduleEntry.planning_week_id,
                ScheduleEntry.date,
                ScheduleEntry.lesson_number,
            )
            .join(GenerationTask, GenerationTask.id == ScheduleEntry.task_id)
            .where(
                GenerationTask.publication_status == "published",
                ScheduleEntry.planning_week_id.in_(week_ids),
                ScheduleEntry.source_stream_id.in_(stream_ids),
                ScheduleEntry.date.is_not(None),
                ScheduleEntry.lesson_number.is_not(None),
            )
        )
        published_slots = {
            (int(stream_id), int(week_id), scheduled_at.date(), int(lesson))
            for stream_id, week_id, scheduled_at, lesson in published_result
            if stream_id is not None and week_id is not None
        }
        published_counts: dict[tuple[int, int], int] = defaultdict(int)
        for stream_id, week_id, _scheduled_on, _lesson in published_slots:
            published_counts[(stream_id, week_id)] += 1

        availability = await build_availability_context(
            db, period.starts_on.isoformat(), period.ends_on.isoformat()
        )
        unavailable = availability["unavailable"]

        def blocked_slots(category: str, resource: str) -> set[tuple[str, int]]:
            return {
                (str(day), int(lesson))
                for day, lesson in unavailable.get(category, {}).get(resource, [])
            }

        week_dates: dict[int, list[date]] = {}
        for week in weeks:
            current = week.starts_on
            dates: list[date] = []
            while current <= week.ends_on:
                if current.weekday() in STUDY_DAYS and current not in holidays:
                    dates.append(current)
                current += timedelta(days=1)
            week_dates[week.id] = dates

        selected_groups = set(groups)
        teacher_names = {
            stream.teacher.name for stream in streams if stream.teacher is not None
        }
        stream_groups = {
            stream.id: sorted(
                {
                    group.group_name
                    for group in stream.groups
                    if group.group_name in selected_groups
                }
            )
            for stream in streams
        }
        teacher_capacity: dict[tuple[str, int], int] = {}
        group_capacity: dict[tuple[str, int], int] = {}
        for week in weeks:
            slots = {
                (current.isoformat(), lesson)
                for current in week_dates[week.id]
                for lesson in GENERATION_LESSONS
            }
            for teacher_name in teacher_names:
                teacher_capacity[(teacher_name, week.id)] = len(
                    slots - blocked_slots("teacher", teacher_name)
                )
            for group_name in selected_groups:
                group_capacity[(group_name, week.id)] = len(
                    slots - blocked_slots("group", group_name)
                )

        streams_by_id = {stream.id: stream for stream in streams}
        for stream_id, week_id, _scheduled_on, _lesson in published_slots:
            stream = streams_by_id[stream_id]
            if stream.teacher:
                key = (stream.teacher.name, week_id)
                teacher_capacity[key] = max(0, teacher_capacity[key] - 1)
            for group_name in stream_groups[stream_id]:
                key = (group_name, week_id)
                group_capacity[key] = max(0, group_capacity[key] - 1)

        allocations: dict[tuple[int, int], int] = {
            (stream.id, week.id): published_counts[(stream.id, week.id)]
            for stream in streams
            for week in weeks
        }
        week_loads: dict[int, int] = {
            week.id: sum(
                published_counts[(stream.id, week.id)] for stream in streams
            )
            for week in weeks
        }
        week_slot_counts = {
            week.id: len(week_dates[week.id]) * len(GENERATION_LESSONS)
            for week in weeks
        }

        def week_overlaps_stream(stream: Stream, week: PlanningWeek) -> bool:
            return not (
                stream.starts_on is not None and stream.starts_on > week.ends_on
            ) and not (stream.ends_on is not None and stream.ends_on < week.starts_on)

        def has_capacity(stream: Stream, week: PlanningWeek) -> bool:
            if not week_dates[week.id] or not week_overlaps_stream(stream, week):
                return False
            if stream.teacher and teacher_capacity[(stream.teacher.name, week.id)] <= 0:
                return False
            return all(
                group_capacity[(group_name, week.id)] > 0
                for group_name in stream_groups[stream.id]
            )

        warnings: list[str] = []
        errors: list[str] = []
        # Allocate the most constrained streams first. Hard availability must
        # take precedence over balancing the total load between weeks.
        streams.sort(
            key=lambda stream: (
                sum(1 for week in weeks if has_capacity(stream, week)),
                -(stream.lessons_count or 0),
                stream.id,
            )
        )
        for stream in streams:
            planned = max(0, int(stream.lessons_count or 0))
            published = sum(
                published_counts[(stream.id, week.id)] for week in weeks
            )
            if published > planned:
                errors.append(
                    f"{stream.event_name}: published {published}, planned {planned}"
                )
                continue
            for _ in range(planned - published):
                candidates = [week for week in weeks if has_capacity(stream, week)]
                if not candidates:
                    missing = planned - sum(
                        allocations[(stream.id, week.id)] for week in weeks
                    )
                    warnings.append(
                        f"{stream.event_name} ({stream.teacher.name if stream.teacher else 'без преподавателя'}): "
                        "не удалось подобрать допустимые слоты для всех пар; "
                        f"останутся не выставленными: {missing}"
                    )
                    # Keep the full workload in weekly demands. The scheduler
                    # will create explicit unassigned entries for lessons that
                    # it cannot place into real slots.
                    fallback_weeks = [
                        week for week in weeks if week_overlaps_stream(stream, week)
                    ]
                    if not fallback_weeks:
                        fallback_weeks = weeks
                    for _ in range(missing):
                        week = min(
                            fallback_weeks,
                            key=lambda item: (
                                allocations[(stream.id, item.id)],
                                Fraction(
                                    week_loads[item.id],
                                    max(1, week_slot_counts[item.id]),
                                ),
                                item.sequence_number,
                            ),
                        )
                        allocations[(stream.id, week.id)] += 1
                        week_loads[week.id] += 1
                    break
                week = min(
                    candidates,
                    key=lambda item: (
                        allocations[(stream.id, item.id)],
                        Fraction(week_loads[item.id], week_slot_counts[item.id]),
                        item.sequence_number,
                    ),
                )
                allocations[(stream.id, week.id)] += 1
                week_loads[week.id] += 1
                if stream.teacher:
                    teacher_capacity[(stream.teacher.name, week.id)] -= 1
                for group_name in stream_groups[stream.id]:
                    group_capacity[(group_name, week.id)] -= 1

        if errors:
            preview = "; ".join(errors[:10])
            if len(errors) > 10:
                preview += f"; и ещё {len(errors) - 10}"
            raise ValueError(f"Semester workload cannot be distributed: {preview}")

        await db.execute(
            delete(WeeklyLessonDemand).where(
                WeeklyLessonDemand.week_id.in_(week_ids),
                WeeklyLessonDemand.stream_id.in_(stream_ids),
            )
        )
        db.add_all(
            [
                WeeklyLessonDemand(
                    week_id=week.id,
                    stream_id=stream.id,
                    lessons_count=allocations[(stream.id, week.id)],
                    priority=priorities.get(stream.id, 5),
                )
                for week in weeks
                for stream in streams
            ]
        )
        await db.commit()

        week_summaries = []
        for week in weeks:
            counts = [allocations[(stream.id, week.id)] for stream in streams]
            week_summaries.append(
                SemesterWeekDistribution(
                    week_id=week.id,
                    sequence_number=week.sequence_number,
                    lessons_count=sum(counts),
                    streams_count=sum(count > 0 for count in counts),
                )
            )
        planned_lessons = sum(max(0, int(stream.lessons_count or 0)) for stream in streams)
        published_lessons = len(published_slots)
        return SemesterDemandDistributionResult(
            period_id=period.id,
            streams_count=len(streams),
            planned_lessons=planned_lessons,
            published_lessons=published_lessons,
            distributed_lessons=sum(item.lessons_count for item in week_summaries),
            warnings=warnings,
            weeks=week_summaries,
        )
