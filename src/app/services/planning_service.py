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
    SubjectScheduleRule,
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
from services.group_relation_service import (
    collect_known_subgroups,
    group_resource_keys,
    parse_group_label,
)
from services.subject_rule_service import applies_to_week, subject_activity_code


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
            .options(
                selectinload(Stream.groups),
                selectinload(Stream.teacher),
                selectinload(Stream.activity_type),
            )
        )
        if enabled_types:
            stream_query = stream_query.where(Stream.stream_type.in_(enabled_types))
        stream_result = await db.execute(stream_query)
        streams = list(stream_result.scalars().unique())
        if not streams:
            raise ValueError("No active streams found for selected groups and types")

        await db.execute(
            select(AcademicPeriod.id)
            .where(AcademicPeriod.id == period_id)
            .with_for_update()
        )
        week_ids = [week.id for week in weeks]
        stream_ids = [stream.id for stream in streams]
        existing_result = await db.execute(
            select(WeeklyLessonDemand).where(
                WeeklyLessonDemand.week_id.in_(week_ids),
                WeeklyLessonDemand.stream_id.in_(stream_ids),
            )
        )
        existing_demands = list(existing_result.scalars())
        priorities: dict[int, int] = {}
        for demand in existing_demands:
            priorities.setdefault(demand.stream_id, demand.priority)
        subject_rules = list(
            (
                await db.execute(
                    select(SubjectScheduleRule).where(
                        SubjectScheduleRule.group_name.in_(groups),
                        SubjectScheduleRule.starts_on <= period.ends_on,
                        SubjectScheduleRule.ends_on >= period.starts_on,
                    )
                )
            ).scalars()
        )
        rule_weeks: dict[tuple[str, str], set[int]] = defaultdict(set)
        for rule in subject_rules:
            rule_weeks[(rule.group_name, rule.subject)].update(
                week.id
                for week in weeks
                if applies_to_week(rule, week.id, week.starts_on, week.ends_on)
            )
        fixed_demand_keys = {
            (stream.id, week_id)
            for stream in streams
            if subject_activity_code(stream)
            for group in stream.groups
            for week_id in rule_weeks.get((group.group_name, stream.event_name), ())
        }
        fixed_demands = {
            (demand.stream_id, demand.week_id): demand.lessons_count
            for demand in existing_demands
            if (demand.stream_id, demand.week_id) in fixed_demand_keys
        }

        published_result = await db.execute(
            select(
                ScheduleEntry.source_stream_id,
                ScheduleEntry.planning_week_id,
                ScheduleEntry.date,
                ScheduleEntry.lesson_number,
                ScheduleEntry.group_name,
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
        published_entries = [
            (stream_id, week_id, scheduled_at.date(), lesson, group_name)
            for stream_id, week_id, scheduled_at, lesson, group_name in published_result
        ]
        published_slots = {
            (stream_id, week_id, scheduled_on, lesson)
            for stream_id, week_id, scheduled_on, lesson, _group in published_entries
        }
        published_counts: dict[tuple[int, int], int] = defaultdict(int)
        for stream_id, week_id, _scheduled_on, _lesson in published_slots:
            published_counts[(stream_id, week_id)] += 1

        availability = await build_availability_context(
            db, period.starts_on.isoformat(), period.ends_on.isoformat()
        )
        unavailable = {
            category: {
                resource: {(day, lesson) for day, lesson in slots}
                for resource, slots in resources.items()
            }
            for category, resources in availability["unavailable"].items()
        }
        blocked_teachers = unavailable["teacher"]
        global_blocks = unavailable["global"].get("*", set())

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
        blocked_groups = {
            label: set().union(
                *(
                    unavailable["group"].get(name, set())
                    for name in (label, *parse_group_label(label).base_groups)
                )
            )
            for label in selected_groups
        }
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
        streams_by_id = {stream.id: stream for stream in streams}
        known_subgroups = collect_known_subgroups(
            selected_groups | {group_name for *_, group_name in published_entries}
        )
        occupied_teacher_slots: dict[str, set[tuple[str, int]]] = defaultdict(set)
        occupied_group_slots: dict[str, set[tuple[str, int]]] = defaultdict(set)
        for stream_id, _week_id, scheduled_on, lesson, group_name in published_entries:
            stream = streams_by_id[stream_id]
            slot = (scheduled_on.isoformat(), lesson)
            if stream.teacher:
                occupied_teacher_slots[stream.teacher.name].add(slot)
            for resource in group_resource_keys(group_name, known_subgroups):
                occupied_group_slots[resource].add(slot)

        for name, blocked in blocked_groups.items():
            for resource in group_resource_keys(name, known_subgroups):
                blocked.update(occupied_group_slots.get(resource, ()))

        teacher_capacity: dict[tuple[str, int], int] = {}
        group_capacity: dict[tuple[str, int], int] = {}
        stream_capacity: dict[tuple[int, int], int] = {}
        shared_streams = {
            stream.id
            for stream in streams
            if subject_activity_code(stream) == "lec"
            or (stream.activity_type and stream.activity_type.is_shared_for_groups)
        }
        for week in weeks:
            slots = {
                (current.isoformat(), lesson)
                for current in week_dates[week.id]
                for lesson in GENERATION_LESSONS
            } - global_blocks
            teacher_slots = {
                name: slots.difference(
                    blocked_teachers.get(name, ()), occupied_teacher_slots[name]
                )
                for name in teacher_names
            }
            group_slots = {
                name: slots - blocked_groups[name] for name in selected_groups
            }
            for teacher_name in teacher_names:
                teacher_capacity[(teacher_name, week.id)] = len(
                    teacher_slots[teacher_name]
                )
            for group_name in selected_groups:
                group_capacity[(group_name, week.id)] = len(group_slots[group_name])
            for stream in streams:
                available = (
                    teacher_slots[stream.teacher.name] if stream.teacher else slots
                )
                audience_slots = [
                    group_slots[name] for name in stream_groups[stream.id]
                ]
                if stream.id in shared_streams:
                    capacity = len(available.intersection(*audience_slots))
                else:
                    cohort_count = max(1, len(audience_slots))
                    per_group = min(
                        (len(available & audience) for audience in audience_slots),
                        default=len(available),
                    )
                    capacity = min(per_group, len(available) // cohort_count)
                stream_capacity[(stream.id, week.id)] = capacity

        stream_teacher_cost = {
            stream.id: (
                1
                if stream.id in shared_streams
                else max(1, len(stream_groups[stream.id]))
            )
            for stream in streams
        }
        allocations: dict[tuple[int, int], int] = {
            (stream.id, week.id): max(
                published_counts[(stream.id, week.id)],
                fixed_demands.get((stream.id, week.id), 0),
            )
            for stream in streams
            for week in weeks
        }
        week_loads: dict[int, int] = {
            week.id: sum(allocations[(stream.id, week.id)] for stream in streams)
            for week in weeks
        }
        for (stream_id, week_id), count in fixed_demands.items():
            remaining = max(0, count - published_counts[(stream_id, week_id)])
            stream = streams_by_id[stream_id]
            if stream.teacher:
                key = (stream.teacher.name, week_id)
                teacher_capacity[key] = max(
                    0, teacher_capacity[key] - remaining * stream_teacher_cost[stream_id]
                )
            for group_name in stream_groups[stream_id]:
                key = (group_name, week_id)
                group_capacity[key] = max(0, group_capacity[key] - remaining)
        week_slot_counts = {
            week.id: len(week_dates[week.id]) * len(GENERATION_LESSONS)
            for week in weeks
        }

        def week_overlaps_stream(stream: Stream, week: PlanningWeek) -> bool:
            return not (
                stream.starts_on is not None and stream.starts_on > week.ends_on
            ) and not (stream.ends_on is not None and stream.ends_on < week.starts_on)

        def has_capacity(stream: Stream, week: PlanningWeek) -> bool:
            key = (stream.id, week.id)
            if (
                key in fixed_demand_keys
                or allocations[key] - published_counts[key] >= stream_capacity[key]
            ):
                return False
            if not week_dates[week.id] or not week_overlaps_stream(stream, week):
                return False
            if (
                stream.teacher
                and teacher_capacity[(stream.teacher.name, week.id)]
                < stream_teacher_cost[stream.id]
            ):
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
            reserved = sum(allocations[(stream.id, week.id)] for week in weeks)
            if reserved > planned:
                errors.append(
                    f"{stream.event_name}: закреплено {reserved}, в плане {planned}"
                )
                continue
            for _ in range(planned - reserved):
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
                        week
                        for week in weeks
                        if (stream.id, week.id) not in fixed_demand_keys
                        and week_overlaps_stream(stream, week)
                    ]
                    if not fallback_weeks:
                        fallback_weeks = [
                            week
                            for week in weeks
                            if (stream.id, week.id) not in fixed_demand_keys
                        ]
                    if not fallback_weeks:
                        warnings.append(
                            f"{stream.event_name}: правила предмета закрепили нагрузку всех недель. Осталось распределить пар: {missing}."
                        )
                        break
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
                    teacher_capacity[(stream.teacher.name, week.id)] -= (
                        stream_teacher_cost[stream.id]
                    )
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
        planned_lessons = sum(
            max(0, int(stream.lessons_count or 0)) for stream in streams
        )
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
