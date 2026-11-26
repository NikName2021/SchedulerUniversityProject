"""Persist and validate subject templates against workload and actual availability."""

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import anyio
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
from ortools.sat.python import cp_model
from schemas.subject_rules import (
    SubjectRuleConfig,
    SubjectRuleContext,
    SubjectRuleWrite,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.availability_service import build_availability_context
from services.group_relation_service import (
    collect_known_subgroups,
    group_resource_keys,
    parse_group_label,
)
from services.scalable_scheduler import solve_event_component

TYPE_FIELDS = {"lec": "lectures", "sem": "seminars", "lab": "laboratories"}
TYPE_LABELS = {"lec": "лекции", "sem": "семинары", "lab": "лабораторные"}


def _cohort_rule_targets(groups: list[str]) -> list[str]:
    """Return leaf group labels so subgroup labs combine with base lectures."""
    known = collect_known_subgroups(groups)
    if not known:
        return list(groups)
    targets = []
    for group in groups:
        parsed = parse_group_label(group)
        if not parsed.subgroup and all(base in known for base in parsed.base_groups):
            continue
        targets.append(group)
    return targets or list(groups)


def subject_activity_code(stream: Stream) -> str | None:
    """Exclude exams and miscellaneous events from the weekly class composition."""
    activity = stream.activity_type
    code = activity.code.casefold().strip() if activity else ""
    label = (activity.name if activity else stream.stream_type or "").casefold().strip()
    if code in {"lecture", "lec"} or "лекц" in label:
        return "lec"
    if code in {"seminar", "sem", "practice", "practical"} or label.startswith(
        ("семинар", "практи")
    ):
        return "sem"
    if code in {"laboratory", "lab"} or "лаборатор" in label:
        return "lab"
    return None


def applies_to_week(
    record: SubjectScheduleRule, week_id: int | None, start: date, end: date
) -> bool:
    if week_id is not None:
        return week_id in json.loads(record.week_ids_json)
    return (
        record.starts_on == start
        and record.ends_on == end
        and not json.loads(record.week_ids_json)
    )


def scope_key(context: SubjectRuleContext) -> str:
    value = [
        context.start_date.isoformat(),
        context.end_date.isoformat(),
        context.week_ids,
    ]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


async def _windows(
    context: SubjectRuleContext, db: AsyncSession, *, lock: bool = False
) -> list:
    if not context.week_ids:
        return [
            SimpleNamespace(
                id=0, starts_on=context.start_date, ends_on=context.end_date
            )
        ]
    query = (
        select(PlanningWeek)
        .where(PlanningWeek.id.in_(context.week_ids))
        .order_by(PlanningWeek.starts_on)
    )
    windows = list((await db.execute(query)).scalars())
    if len(windows) != len(context.week_ids):
        raise LookupError("Учебная неделя не найдена")
    if len({week.period_id for week in windows}) != 1:
        raise ValueError("Выберите недели одного учебного периода")
    if any(
        week.starts_on < context.start_date or week.ends_on > context.end_date
        for week in windows
    ):
        raise ValueError("Выбранные недели выходят за границы периода")
    if lock:
        # Serialize changes to the same semester budget, including non-overlapping weeks.
        await db.execute(
            select(AcademicPeriod.id)
            .where(AcademicPeriod.id == windows[0].period_id)
            .with_for_update()
        )
    return windows


async def _streams(
    context: SubjectRuleContext, db: AsyncSession, subject: str | None = None
) -> list[Stream]:
    query = (
        select(Stream)
        .join(Stream.groups)
        .where(StreamGroup.group_name.in_(context.groups), Stream.is_ignored.is_(False))
        .options(
            selectinload(Stream.groups),
            selectinload(Stream.teacher),
            selectinload(Stream.activity_type),
        )
    )
    if subject is not None:
        query = query.where(Stream.event_name == subject)
    if context.enabled_types:
        query = query.where(Stream.stream_type.in_(context.enabled_types))
    return [
        stream
        for stream in (await db.execute(query)).scalars().unique()
        if subject_activity_code(stream)
    ]


async def list_subject_rules(
    context: SubjectRuleContext, db: AsyncSession
) -> dict[str, Any]:
    windows = await _windows(context, db)
    streams = await _streams(context, db)
    records = list(
        (
            await db.execute(
                select(SubjectScheduleRule)
                .where(
                    SubjectScheduleRule.group_name.in_(context.groups),
                    SubjectScheduleRule.starts_on <= context.end_date,
                    SubjectScheduleRule.ends_on >= context.start_date,
                )
                .order_by(
                    SubjectScheduleRule.updated_at.desc(), SubjectScheduleRule.id.desc()
                )
            )
        ).scalars()
    )
    items = []
    for subject in sorted({stream.event_name for stream in streams}):
        matching = [stream for stream in streams if stream.event_name == subject]
        groups = sorted(
            {
                group.group_name
                for stream in matching
                for group in stream.groups
                if group.group_name in context.groups
            }
        )
        active = [
            next(
                (
                    record
                    for record in records
                    if record.subject == subject
                    and record.group_name == group
                    and applies_to_week(
                        record, week.id or None, week.starts_on, week.ends_on
                    )
                ),
                None,
            )
            for group in groups
            for week in windows
        ]
        saved = [record for record in active if record is not None]
        counts = {
            field: int(
                any(subject_activity_code(stream) == code for stream in matching)
            )
            for code, field in TYPE_FIELDS.items()
        }
        config = (
            json.loads(saved[0].config_json)
            if saved
            else SubjectRuleConfig(
                **counts, days_per_week=min(2, sum(counts.values()))
            ).model_dump()
        )
        signatures = {record.config_json if record else None for record in active}
        items.append(
            {
                "subject": subject,
                "groups": groups,
                "rule": config,
                "saved": bool(saved),
                "mixed": len(signatures) > 1,
            }
        )
    return {"items": items}


async def _locked_outside_weeks(
    payload: SubjectRuleWrite,
    period_weeks: list,
    streams: list[Stream],
    db: AsyncSession,
) -> tuple[dict[tuple[int, int], int], dict[int, set[int]]]:
    """Return published lesson counts and rule-locked week ids outside target weeks."""
    outside_week_ids = [
        week.id for week in period_weeks if week.id not in payload.week_ids
    ]
    if not outside_week_ids:
        return {}, defaultdict(set)
    ids = [stream.id for stream in streams]
    published_outside: dict[tuple[int, int], set[tuple[Any, int]]] = defaultdict(set)
    published_result = await db.execute(
        select(
            ScheduleEntry.source_stream_id,
            ScheduleEntry.planning_week_id,
            ScheduleEntry.date,
            ScheduleEntry.lesson_number,
        )
        .join(GenerationTask)
        .where(
            GenerationTask.publication_status == "published",
            ScheduleEntry.planning_week_id.in_(outside_week_ids),
            ScheduleEntry.source_stream_id.in_(ids),
            ScheduleEntry.date.is_not(None),
            ScheduleEntry.lesson_number.is_not(None),
        )
    )
    for stream_id, week_id, day, lesson in published_result:
        published_outside[(stream_id, week_id)].add((day, lesson))

    outside_weeks = [week for week in period_weeks if week.id in outside_week_ids]
    min_start = min(week.starts_on for week in outside_weeks)
    max_end = max(week.ends_on for week in outside_weeks)
    existing_rules = list(
        (
            await db.execute(
                select(SubjectScheduleRule).where(
                    SubjectScheduleRule.subject == payload.subject,
                    SubjectScheduleRule.group_name.in_(payload.groups),
                    SubjectScheduleRule.starts_on <= max_end,
                    SubjectScheduleRule.ends_on >= min_start,
                )
            )
        ).scalars()
    )
    locked_by_group: dict[str, set[int]] = defaultdict(set)
    for record in existing_rules:
        for week in outside_weeks:
            if applies_to_week(record, week.id, week.starts_on, week.ends_on):
                locked_by_group[record.group_name].add(week.id)

    locked_by_stream: dict[int, set[int]] = defaultdict(set)
    for stream in streams:
        for group in stream.groups:
            locked_by_stream[stream.id].update(
                locked_by_group.get(group.group_name, ())
            )
    return (
        {key: len(slots) for key, slots in published_outside.items()},
        locked_by_stream,
    )


def _allocation_error_message(
    payload: SubjectRuleWrite,
    windows: list,
    streams: list[Stream],
    outside_locked: dict[int, int],
) -> str:
    participating = {
        group.group_name for stream in streams for group in stream.groups
    } & set(payload.groups)
    known = collect_known_subgroups(participating)
    stream_cohorts = {
        stream.id: {
            resource
            for group in stream.groups
            if group.group_name in participating
            for resource in group_resource_keys(group.group_name, known)
        }
        for stream in streams
    }
    all_cohorts = sorted(
        {cohort for cohorts in stream_cohorts.values() for cohort in cohorts}
    )
    shortfalls = []
    for code, field in TYPE_FIELDS.items():
        needed = getattr(payload.rule, field) * len(windows)
        if needed <= 0:
            continue
        min_available: int | None = None
        for cohort in all_cohorts:
            available = sum(
                max(0, int(stream.lessons_count or 0) - outside_locked[stream.id])
                for stream in streams
                if subject_activity_code(stream) == code
                and cohort in stream_cohorts[stream.id]
            )
            min_available = (
                available if min_available is None else min(min_available, available)
            )
        if min_available is not None and min_available < needed:
            shortfalls.append(
                f"{TYPE_LABELS[code]}: нужно {needed} на {len(windows)} нед., доступно {min_available}"
            )
    if shortfalls:
        details = "; ".join(shortfalls)
        hint = (
            " Выберите конкретную неделю в «Период действия» или уменьшите число пар."
            if len(windows) > 1
            else " Уменьшите число пар или проверьте опубликованные/закреплённые недели."
        )
        return f"Схема не укладывается в учебный план ({details}).{hint}"
    return (
        "Схема не укладывается в учебный план: проверьте число пар, нагрузку остальных недель и опубликованные занятия. "
        "Для общего потока выберите все его группы."
    )


async def _allocate(
    payload: SubjectRuleWrite, windows: list, streams: list[Stream], db: AsyncSession
) -> tuple[dict, list[str]]:
    """Allocate one count per stream/week, respecting shared groups and semester totals."""
    if not streams:
        return {}, ["Для этого предмета нет активных потоков в выбранных группах"]
    if len(streams) > 500:
        return {}, ["Слишком много потоков: выберите меньше групп"]
    ids = [stream.id for stream in streams]
    period_weeks = windows
    if payload.week_ids:
        period_weeks = list(
            (
                await db.execute(
                    select(PlanningWeek).where(
                        PlanningWeek.period_id == windows[0].period_id
                    )
                )
            ).scalars()
        )
    demands = (
        list(
            (
                await db.execute(
                    select(WeeklyLessonDemand).where(
                        WeeklyLessonDemand.stream_id.in_(ids),
                        WeeklyLessonDemand.week_id.in_(
                            [week.id for week in period_weeks]
                        ),
                    )
                )
            ).scalars()
        )
        if payload.week_ids
        else []
    )
    baseline = {(item.stream_id, item.week_id): item.lessons_count for item in demands}
    published_outside, locked_outside = (
        await _locked_outside_weeks(payload, period_weeks, streams, db)
        if payload.week_ids
        else ({}, defaultdict(set))
    )
    outside_locked = defaultdict(int)
    for demand in demands:
        if demand.week_id in payload.week_ids:
            continue
        pub_count = published_outside.get((demand.stream_id, demand.week_id), 0)
        if demand.week_id in locked_outside.get(demand.stream_id, ()):
            outside_locked[demand.stream_id] += max(pub_count, demand.lessons_count)
        elif pub_count:
            outside_locked[demand.stream_id] += pub_count
    for (stream_id, week_id), pub_count in published_outside.items():
        if (stream_id, week_id) not in baseline:
            outside_locked[stream_id] += pub_count

    published = defaultdict(set)
    if payload.week_ids:
        result = await db.execute(
            select(
                ScheduleEntry.source_stream_id,
                ScheduleEntry.planning_week_id,
                ScheduleEntry.date,
                ScheduleEntry.lesson_number,
            )
            .join(GenerationTask)
            .where(
                GenerationTask.publication_status == "published",
                ScheduleEntry.planning_week_id.in_(payload.week_ids),
                ScheduleEntry.source_stream_id.in_(ids),
                ScheduleEntry.date.is_not(None),
                ScheduleEntry.lesson_number.is_not(None),
            )
        )
        for stream_id, week_id, day, lesson in result:
            published[(stream_id, week_id)].add((day, lesson))

    def solve() -> dict | None:
        model = cp_model.CpModel()
        variables = {}
        changes = []
        for stream in streams:
            for week in windows:
                variable = model.NewIntVar(0, 14, f"load_{stream.id}_{week.id}")
                variables[(stream.id, week.id)] = variable
                if (stream.starts_on and stream.starts_on > week.ends_on) or (
                    stream.ends_on and stream.ends_on < week.starts_on
                ):
                    model.Add(variable == 0)
                model.Add(variable >= len(published[(stream.id, week.id)]))
                if payload.week_ids and any(
                    group.group_name not in payload.groups for group in stream.groups
                ):
                    # A stream is a shared workload. Never change another group's plan implicitly.
                    model.Add(variable == baseline.get((stream.id, week.id), 0))
                elif not payload.week_ids and any(
                    group.group_name not in payload.groups for group in stream.groups
                ):
                    model.Add(variable == (stream.lessons_count or 0))
                delta = model.NewIntVar(0, 10000, f"change_{stream.id}_{week.id}")
                model.AddAbsEquality(
                    delta, variable - baseline.get((stream.id, week.id), 0)
                )
                changes.append(delta)
            model.Add(
                sum(variables[(stream.id, week.id)] for week in windows)
                <= max(0, int(stream.lessons_count or 0) - outside_locked[stream.id])
            )
        participating = {
            group.group_name for stream in streams for group in stream.groups
        } & set(payload.groups)
        known_subgroups = collect_known_subgroups(participating)
        stream_cohorts = {
            stream.id: {
                resource
                for group in stream.groups
                if group.group_name in participating
                for resource in group_resource_keys(group.group_name, known_subgroups)
            }
            for stream in streams
        }
        all_cohorts = sorted(
            {cohort for cohorts in stream_cohorts.values() for cohort in cohorts}
        )
        for cohort in all_cohorts:
            for code, field in TYPE_FIELDS.items():
                matching = [
                    stream
                    for stream in streams
                    if subject_activity_code(stream) == code
                    and cohort in stream_cohorts[stream.id]
                ]
                for week in windows:
                    model.Add(
                        sum(variables[(stream.id, week.id)] for stream in matching)
                        == getattr(payload.rule, field)
                    )
        model.Minimize(sum(changes))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 2
        solver.parameters.num_search_workers = 1
        if solver.Solve(model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        return {
            str(week.id): {
                str(stream.id): solver.Value(variables[(stream.id, week.id)])
                for stream in streams
            }
            for week in windows
        }

    result = await anyio.to_thread.run_sync(solve)
    if result is None:
        return {}, [_allocation_error_message(payload, windows, streams, outside_locked)]
    return result, []


def _events(streams: list[Stream], counts: dict, groups: list[str]) -> list[dict]:
    known = collect_known_subgroups(groups)
    result = []
    for stream in streams:
        count = counts.get(str(stream.id), 0)
        if not count:
            continue
        selected = sorted({group.group_name for group in stream.groups} & set(groups))
        shared = subject_activity_code(stream) == "lec" or bool(
            stream.activity_type and stream.activity_type.is_shared_for_groups
        )
        for cohort in [selected] if shared else [[group] for group in selected]:
            base_groups = sorted(
                {
                    base
                    for group in cohort
                    for base in parse_group_label(group).base_groups
                }
            )
            result.append(
                {
                    "id": f"rule:{stream.id}:{','.join(cohort)}",
                    "stream_id": stream.id,
                    "subject": stream.event_name,
                    "type": subject_activity_code(stream),
                    "stream_type": stream.stream_type,
                    "teacher": stream.teacher.name if stream.teacher else None,
                    "teacher_id": stream.teacher_id,
                    "groups": cohort,
                    "base_groups": base_groups,
                    "group_resources": sorted(
                        {
                            resource
                            for group in cohort
                            for resource in group_resource_keys(group, known)
                        }
                    ),
                    "lessons_count": count,
                    "priority": 5,
                }
            )
    return result


def _teacher_day_conflict(
    rule: SubjectRuleConfig,
    events: list[dict],
    week_start: date,
    week_end: date,
    holidays: list[date],
    teacher_unavailable: dict,
) -> str | None:
    teachers = {event["teacher"] for event in events}
    if (
        not rule.days_hard
        or len(rule.weekdays) != rule.days_per_week
        or len(teachers) != 1
    ):
        return None
    teacher = next(iter(teachers))
    blocked = {tuple(slot) for slot in teacher_unavailable.get(teacher, [])}
    for weekday in rule.weekdays:
        day = week_start + timedelta(days=(weekday - week_start.weekday()) % 7)
        if day > week_end or day in holidays:
            continue
        if all(
            (weekday, lesson) in blocked or (day.isoformat(), lesson) in blocked
            for lesson in GENERATION_LESSONS
        ):
            return (
                f"{day:%d.%m} преподаватель недоступен. "
                "Выберите другой день или укажите его как пожелание"
            )
    return None


async def check_subject_rule(
    payload: SubjectRuleWrite, db: AsyncSession, *, save: bool = False
) -> dict[str, Any]:
    windows = await _windows(payload, db, lock=save)
    streams = await _streams(payload, db, payload.subject)
    counts, errors = await _allocate(payload, windows, streams, db)
    result: dict[str, Any] = {
        "can_save": False,
        "errors": errors,
        "warnings": [],
        "preview": [],
        "total_per_week": payload.rule.lectures
        + payload.rule.seminars
        + payload.rule.laboratories,
        "weekly_counts": counts,
    }
    if errors:
        return result
    availability = await build_availability_context(
        db, payload.start_date.isoformat(), payload.end_date.isoformat()
    )
    teacher_names = {stream.teacher.name for stream in streams if stream.teacher}
    relevant_groups = {
        base
        for group in payload.groups
        for base in parse_group_label(group).base_groups
    } | set(payload.groups)
    unavailable = {
        "teacher": {
            name: slots
            for name, slots in availability["unavailable"]["teacher"].items()
            if name in teacher_names
        },
        "group": {
            name: slots
            for name, slots in availability["unavailable"]["group"].items()
            if name in relevant_groups
        },
        "global": availability["unavailable"]["global"],
    }
    participating = sorted(
        {group.group_name for stream in streams for group in stream.groups}
        & set(payload.groups)
    )
    rules = [
        {
            "subject": payload.subject,
            "group_name": group,
            "rule": payload.rule.model_dump(),
        }
        for group in _cohort_rule_targets(participating)
    ]
    cache = {}
    for week in windows:
        events = _events(streams, counts[str(week.id)], payload.groups)
        context = {
            "start_date": week.starts_on.isoformat(),
            "end_date": week.ends_on.isoformat(),
            "immutable_before": week.starts_on.isoformat(),
            "holidays": [day.isoformat() for day in payload.holidays],
            "study_days": STUDY_DAYS,
            "lessons": GENERATION_LESSONS,
            "unavailable": unavailable,
            "subject_rules": rules,
            "max_time_seconds": 1,
            "num_workers": 1,
            "require_full_placement": True,
            "rule_settings": {"minimize_windows": {"enabled": False}},
        }
        pattern = []
        for category in ("teacher", "group", "global"):
            for resource, slots in unavailable.get(category, {}).items():
                for day, lesson in slots:
                    if isinstance(day, str):
                        current = date.fromisoformat(day)
                        if not week.starts_on <= current <= week.ends_on:
                            continue
                        day = current.weekday()
                    pattern.append((category, resource, day, lesson))
        signature = json.dumps(
            [
                counts[str(week.id)],
                sorted(pattern),
                week.starts_on.weekday(),
                (week.ends_on - week.starts_on).days,
                [
                    day.weekday()
                    for day in payload.holidays
                    if week.starts_on <= day <= week.ends_on
                ],
            ],
            sort_keys=True,
        )
        if signature not in cache:
            cache[signature] = await anyio.to_thread.run_sync(
                lambda e=events, c=context: solve_event_component(e, c)
            )
        solved = cache[signature]
        if solved["status"] != "success" or solved.get("unassigned"):
            state = solved.get("metrics", {}).get("solver_status")
            if state == "UNKNOWN":
                reason = "Не удалось завершить проверку. Повторите её"
            else:
                reason = (
                    _teacher_day_conflict(
                        payload.rule,
                        events,
                        week.starts_on,
                        week.ends_on,
                        payload.holidays,
                        unavailable["teacher"],
                    )
                    or "Не хватает доступных пар для выбранного состава занятий, дней и порядка лекций"
                )
            result["errors"].append(
                f"{week.starts_on:%d.%m}–{week.ends_on:%d.%m}: {reason}."
            )
        elif not result["preview"]:
            result["preview"] = [
                {
                    "date": item["slot"][0],
                    "lesson_number": item["slot"][1],
                    "type": item["type"],
                    "groups": item["groups"],
                }
                for item in solved["assignments"]
            ]
        if len(result["errors"]) >= 5:
            break
    if not payload.rule.days_hard and result["preview"]:
        for group in participating:
            days = {
                item["date"] for item in result["preview"] if group in item["groups"]
            }
            if len(days) != payload.rule.days_per_week or (
                payload.rule.weekdays
                and any(
                    date.fromisoformat(day).weekday() not in payload.rule.weekdays
                    for day in days
                )
            ):
                result["warnings"].append(
                    "Пожелания по дням могут быть выполнены не полностью. Недоступность преподавателей остаётся обязательным ограничением."
                )
                break
    result["can_save"] = not result["errors"]
    if save and result["can_save"]:
        key = scope_key(payload)
        existing = {
            (record.group_name): record
            for record in (
                await db.execute(
                    select(SubjectScheduleRule).where(
                        SubjectScheduleRule.subject == payload.subject,
                        SubjectScheduleRule.group_name.in_(participating),
                        SubjectScheduleRule.scope_key == key,
                    )
                )
            ).scalars()
        }
        for group in participating:
            record = existing.get(group)
            if record is None:
                record = SubjectScheduleRule(
                    group_name=group,
                    subject=payload.subject,
                    scope_key=key,
                    starts_on=payload.start_date,
                    ends_on=payload.end_date,
                )
                db.add(record)
            record.week_ids_json = json.dumps(payload.week_ids)
            record.config_json = payload.rule.model_dump_json()
            record.updated_at = datetime.utcnow()
        if payload.week_ids:
            period_weeks = list(
                (
                    await db.execute(
                        select(PlanningWeek)
                        .where(PlanningWeek.period_id == windows[0].period_id)
                        .order_by(PlanningWeek.starts_on)
                    )
                ).scalars()
            )
            all_week_ids = [week.id for week in period_weeks]
            demands = {
                (item.stream_id, item.week_id): item
                for item in (
                    await db.execute(
                        select(WeeklyLessonDemand).where(
                            WeeklyLessonDemand.week_id.in_(all_week_ids),
                            WeeklyLessonDemand.stream_id.in_(
                                [stream.id for stream in streams]
                            ),
                        )
                    )
                ).scalars()
            }
            for week_id, stream_counts in counts.items():
                for stream_id, count in stream_counts.items():
                    demand = demands.get((int(stream_id), int(week_id)))
                    if demand is None:
                        demand = WeeklyLessonDemand(
                            stream_id=int(stream_id), week_id=int(week_id), priority=5
                        )
                        db.add(demand)
                        demands[(int(stream_id), int(week_id))] = demand
                    demand.lessons_count = count
            published_outside, locked_outside = await _locked_outside_weeks(
                payload, period_weeks, streams, db
            )
            outside_week_ids = [
                week.id
                for week in reversed(period_weeks)
                if week.id not in payload.week_ids
            ]
            for stream in streams:
                planned = max(0, int(stream.lessons_count or 0))
                total_assigned = sum(
                    demands[(stream.id, week_id)].lessons_count
                    for week_id in all_week_ids
                    if (stream.id, week_id) in demands
                )
                excess = total_assigned - planned
                if excess <= 0:
                    continue
                locked_weeks = locked_outside.get(stream.id, set())
                for week_id in outside_week_ids:
                    if excess <= 0:
                        break
                    if week_id in locked_weeks:
                        continue
                    demand = demands.get((stream.id, week_id))
                    if demand is None or demand.lessons_count <= 0:
                        continue
                    floor = published_outside.get((stream.id, week_id), 0)
                    reducible = max(0, demand.lessons_count - floor)
                    if reducible <= 0:
                        continue
                    take = min(excess, reducible)
                    demand.lessons_count -= take
                    excess -= take
        await db.commit()
    return result


async def generation_subject_rules(
    context: SubjectRuleContext, db: AsyncSession
) -> tuple[list[dict], dict[str, int]]:
    """Freeze effective saved rules and standalone counts into a generation task."""
    records = list(
        (
            await db.execute(
                select(SubjectScheduleRule)
                .where(
                    SubjectScheduleRule.group_name.in_(context.groups),
                    SubjectScheduleRule.starts_on <= context.start_date,
                    SubjectScheduleRule.ends_on >= context.end_date,
                )
                .order_by(
                    SubjectScheduleRule.updated_at.desc(), SubjectScheduleRule.id.desc()
                )
            )
        ).scalars()
    )
    week_id = context.week_ids[0] if context.week_ids else None
    effective = {}
    for record in records:
        if applies_to_week(record, week_id, context.start_date, context.end_date):
            effective.setdefault((record.subject, record.group_name), record)

    groups_by_rule = defaultdict(list)
    for (subject, group), record in effective.items():
        groups_by_rule[(subject, record.config_json)].append(group)
    rules = []
    overrides: dict[str, int] = {}
    for (subject, config_json), groups in groups_by_rule.items():
        config = SubjectRuleConfig.model_validate_json(config_json)
        payload = SubjectRuleWrite(
            **{**context.model_dump(), "groups": groups}, subject=subject, rule=config
        )
        streams = await _streams(payload, db, subject)
        if not streams:
            continue
        if week_id is not None:
            actual = {
                item.stream_id: item.lessons_count
                for item in (
                    await db.execute(
                        select(WeeklyLessonDemand).where(
                            WeeklyLessonDemand.week_id == week_id,
                            WeeklyLessonDemand.stream_id.in_(
                                [stream.id for stream in streams]
                            ),
                        )
                    )
                ).scalars()
            }
            known_subgroups = collect_known_subgroups(groups)
            stream_cohorts = {
                stream.id: {
                    resource
                    for item in stream.groups
                    if item.group_name in groups
                    for resource in group_resource_keys(
                        item.group_name, known_subgroups
                    )
                }
                for stream in streams
            }
            all_cohorts = sorted(
                {cohort for cohorts in stream_cohorts.values() for cohort in cohorts}
            )
            for cohort in all_cohorts:
                composition = defaultdict(int)
                for stream in streams:
                    if cohort in stream_cohorts[stream.id]:
                        composition[subject_activity_code(stream)] += actual.get(
                            stream.id, 0
                        )
                if any(
                    composition[code] != getattr(config, field)
                    for code, field in TYPE_FIELDS.items()
                ):
                    group_label = cohort.split("::", 1)[0]
                    raise ValueError(
                        f"{subject}, {group_label}: недельная нагрузка или выбранные типы занятий изменились. Проверьте правило."
                    )
            overrides.update(
                {str(stream.id): actual.get(stream.id, 0) for stream in streams}
            )
        else:
            # A standalone week does not modify the semester plan.
            counts, errors = await _allocate(
                payload, await _windows(payload, db), streams, db
            )
            if errors:
                raise ValueError(f"{subject}: {' '.join(errors)}")
            for stream_id, count in counts["0"].items():
                if stream_id in overrides and overrides[stream_id] != count:
                    raise ValueError(
                        f"{subject}: для общего потока заданы разные схемы занятий"
                    )
                overrides[stream_id] = count
        rules.extend(
            {"subject": subject, "group_name": group, "rule": config.model_dump()}
            for group in _cohort_rule_targets(groups)
        )
    return rules, overrides
