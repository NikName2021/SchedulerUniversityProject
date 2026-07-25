from __future__ import annotations

import collections
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from core.config import sessionmaker
from core.constants import (
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    LESSONS,
    MAX_ESTIMATED_DECISION_VARIABLES,
    MAX_GENERATION_HORIZON_DAYS,
    MAX_TIME_SECONDS,
    NUM_WORKERS,
    STUDY_DAYS,
)
from core.constants import ROOMS as DEFAULT_ROOMS
from database import (
    GenerationComponent,
    GenerationIssue,
    GenerationLock,
    GenerationTask,
    Room,
    RoomFeatureLink,
    RuleProfile,
    ScheduleEntry,
    Stream,
    StreamFeatureRequirement,
    StreamGroup,
    WeeklyLessonDemand,
)
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import selectinload

from services.availability_service import build_availability_context
from services.scalable_scheduler import assign_rooms_matching, build_conflict_components

logger = logging.getLogger(__name__)

TYPE_CODES = {
    "лекция": "lec",
    "семинар": "sem",
    "практика": "sem",
    "практическая": "sem",
    "зачет": "sem",
    "экзамен": "sem",
    "лабораторная": "lab",
    "лабораторная работа": "lab",
}


def _type_code(stream_type: str | None) -> str | None:
    normalized = (stream_type or "").strip().lower()
    if "лекц" in normalized:
        return "lec"
    if "лаборатор" in normalized:
        return "lab"
    return TYPE_CODES.get(normalized, "sem" if normalized else None)


def _activity_code(stream: Stream) -> str | None:
    if stream.activity_type:
        code = stream.activity_type.code.strip().lower()
        if code in {"lecture", "lec"}:
            return "lec"
        if code in {"laboratory", "lab"}:
            return "lab"
        return "sem"
    return _type_code(stream.stream_type)


def _teacher_unavailable(
    stream: Stream, start_date: str, end_date: str
) -> list[list[Any]]:
    if not stream.teacher or not stream.teacher.restrictions_json:
        return []
    try:
        restrictions = json.loads(stream.teacher.restrictions_json)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(restrictions, dict):
        return []

    recurring: list[list[Any]] = []
    for raw_value in restrictions.get("recurring", []):
        value = str(raw_value)
        for separator in ("-", "_", ":"):
            if separator not in value:
                continue
            try:
                js_day, lesson = value.split(separator, 1)
                recurring.append([(int(js_day) - 1) % 7, int(lesson)])
                break
            except ValueError:
                continue

    specific: list[list[Any]] = []
    for raw_value in restrictions.get("specific", []):
        value = str(raw_value)
        try:
            date_string, lesson = value.rsplit("-", 1)
            datetime.strptime(date_string, "%Y-%m-%d")
            specific.append([date_string, int(lesson)])
        except ValueError:
            continue

    mode = restrictions.get("mode", "blacklist")
    if mode != "whitelist":
        return recurring + specific

    allowed_recurring = {(int(day), int(lesson)) for day, lesson in recurring}
    allowed_specific = {(str(day), int(lesson)) for day, lesson in specific}
    unavailable = []
    current = datetime.fromisoformat(start_date).date()
    last_date = datetime.fromisoformat(end_date).date()
    while current <= last_date:
        if current.weekday() in STUDY_DAYS:
            for lesson in LESSONS:
                if (current.weekday(), lesson) not in allowed_recurring and (
                    current.isoformat(),
                    lesson,
                ) not in allowed_specific:
                    unavailable.append([current.isoformat(), lesson])
        current += timedelta(days=1)
    return unavailable


class ScalableGenerationService:
    @staticmethod
    async def prepare(
        task_id: int,
        selected_groups: list[str],
        holidays: list[str],
        enabled_types: list[str],
        start_date: str | None,
        end_date: str | None,
        planning_week_id: int | None,
    ) -> dict[str, Any] | None:
        async with sessionmaker() as session:
            task = await session.get(GenerationTask, task_id)
            if task is None:
                return None
            if task.status in {"success", "partial", "failed", "canceled"}:
                return None

            task.status = "running"
            task.error_message = None
            task.completed_components = 0
            task.progress_percent = 1
            await session.execute(
                delete(GenerationComponent).where(
                    GenerationComponent.task_id == task_id
                )
            )

            settings = json.loads(task.settings_json or "{}")
            start_date = start_date or DEFAULT_START_DATE.isoformat()
            end_date = end_date or DEFAULT_END_DATE.isoformat()
            horizon_days = (
                date.fromisoformat(end_date) - date.fromisoformat(start_date)
            ).days + 1
            if horizon_days > MAX_GENERATION_HORIZON_DAYS:
                task.status = "failed"
                task.progress_percent = 100
                task.error_message = (
                    f"Generation horizon is too large: {horizon_days} days. "
                    f"Use a planning week or a range up to "
                    f"{MAX_GENERATION_HORIZON_DAYS} days."
                )
                await session.execute(
                    delete(GenerationLock).where(GenerationLock.task_id == task_id)
                )
                await session.commit()
                return None
            weekly_counts: dict[int, int] = {}
            weekly_priorities: dict[int, int] = {}
            if planning_week_id is not None:
                result = await session.execute(
                    select(WeeklyLessonDemand).where(
                        WeeklyLessonDemand.week_id == planning_week_id
                    )
                )
                demands = list(result.scalars())
                if not demands:
                    task.status = "failed"
                    task.error_message = (
                        "Weekly lesson demand is not configured for this week"
                    )
                    await session.execute(
                        delete(GenerationLock).where(GenerationLock.task_id == task_id)
                    )
                    await session.commit()
                    return None
                weekly_counts = {
                    demand.stream_id: demand.lessons_count for demand in demands
                }
                weekly_priorities = {
                    demand.stream_id: demand.priority for demand in demands
                }

            query = (
                select(Stream)
                .join(Stream.groups)
                .where(StreamGroup.group_name.in_(selected_groups))
                .where(Stream.is_ignored.is_(False))
                .where(
                    or_(
                        Stream.starts_on.is_(None),
                        Stream.starts_on <= date.fromisoformat(end_date),
                    ),
                    or_(
                        Stream.ends_on.is_(None),
                        Stream.ends_on >= date.fromisoformat(start_date),
                    ),
                )
                .options(
                    selectinload(Stream.groups),
                    selectinload(Stream.teacher),
                    selectinload(Stream.activity_type),
                    selectinload(Stream.discipline),
                    selectinload(Stream.required_room),
                    selectinload(Stream.feature_requirements).selectinload(
                        StreamFeatureRequirement.feature
                    ),
                )
            )
            affected_stream_ids = {
                int(stream_id) for stream_id in settings.get("affected_stream_ids", [])
            }
            base_task_id = settings.get("base_task_id")
            if affected_stream_ids and not base_task_id:
                task.status = "failed"
                task.error_message = (
                    "base_task_id is required when affected_stream_ids are provided"
                )
                await session.execute(
                    delete(GenerationLock).where(GenerationLock.task_id == task_id)
                )
                await session.commit()
                return None
            if enabled_types:
                query = query.where(Stream.stream_type.in_(enabled_types))
            if affected_stream_ids:
                query = query.where(Stream.id.in_(affected_stream_ids))
            if planning_week_id is not None:
                active_ids = [
                    stream_id for stream_id, count in weekly_counts.items() if count > 0
                ]
                query = query.where(Stream.id.in_(active_ids))
            result = await session.execute(query)
            streams = list(result.scalars().unique())
            if not streams:
                task.status = "failed"
                task.error_message = "No active streams found for selected groups"
                await session.execute(
                    delete(GenerationLock).where(GenerationLock.task_id == task_id)
                )
                await session.commit()
                return None

            room_result = await session.execute(
                select(Room)
                .where(Room.is_active.is_(True))
                .options(
                    selectinload(Room.feature_links).selectinload(
                        RoomFeatureLink.feature
                    )
                )
                .order_by(Room.code)
            )
            db_rooms = list(room_result.scalars().unique())
            rooms = {
                room.code: {
                    "id": room.id,
                    "capacity": room.capacity,
                    "type": room.room_type,
                    "features": [link.feature.code for link in room.feature_links],
                }
                for room in db_rooms
            }
            if not rooms:
                rooms = {
                    code: {**details, "id": None, "features": []}
                    for code, details in DEFAULT_ROOMS.items()
                }

            availability = await build_availability_context(
                session, start_date, end_date
            )
            profile_id = settings.get("rule_profile_id")
            profile_query = select(RuleProfile).options(
                selectinload(RuleProfile.settings)
            )
            if profile_id is not None:
                profile_query = profile_query.where(
                    RuleProfile.id == int(profile_id), RuleProfile.is_active.is_(True)
                )
            else:
                profile_query = profile_query.where(
                    RuleProfile.is_default.is_(True), RuleProfile.is_active.is_(True)
                )
            profile = (await session.execute(profile_query)).scalar_one_or_none()
            rule_settings = {
                item.rule_code: {
                    "enabled": item.enabled,
                    "is_hard": item.is_hard,
                    "weight": item.weight,
                }
                for item in (profile.settings if profile else [])
            }

            selected_stream_ids = {stream.id for stream in streams}
            fixed_by_stream_group: dict[tuple[int, str], list[Any]] = {}
            fixed_by_stream: dict[int, list[Any]] = {}
            carry_over_entries: list[dict[str, Any]] = []
            occupied_groups: dict[str, list[list[Any]]] = collections.defaultdict(list)
            occupied_teachers: dict[str, list[list[Any]]] = collections.defaultdict(
                list
            )
            occupied_rooms: dict[str, list[list[Any]]] = collections.defaultdict(list)
            if planning_week_id is not None:
                entries_query = (
                    select(ScheduleEntry)
                    .where(
                        ScheduleEntry.planning_week_id == planning_week_id,
                        ScheduleEntry.source_stream_id.is_not(None),
                    )
                    .options(selectinload(ScheduleEntry.teacher))
                )
                if base_task_id:
                    entries_query = entries_query.where(
                        ScheduleEntry.task_id == int(base_task_id)
                    )
                else:
                    entries_query = entries_query.where(
                        ScheduleEntry.is_locked.is_(True)
                    )
                fixed_result = await session.execute(entries_query)
                for entry in fixed_result.scalars():
                    if entry.date is None or entry.lesson_number is None:
                        continue
                    slot = [entry.date.date().isoformat(), entry.lesson_number]
                    if (
                        entry.source_stream_id in selected_stream_ids
                        and entry.is_locked
                    ):
                        fixed_by_stream_group[
                            (entry.source_stream_id, entry.group_name)
                        ] = slot
                        fixed_by_stream[entry.source_stream_id] = slot
                        continue
                    if entry.source_stream_id in selected_stream_ids:
                        continue

                    carry_over_entries.append(
                        {
                            "source_stream_id": entry.source_stream_id,
                            "group_name": entry.group_name,
                            "event_name": entry.event_name,
                            "stream_type": entry.stream_type,
                            "teacher_id": entry.teacher_id,
                            "room_id": entry.room_id,
                            "room_ref_id": entry.room_ref_id,
                            "date": entry.date.date().isoformat(),
                            "lesson_number": entry.lesson_number,
                            "warning": entry.warning,
                            "is_locked": entry.is_locked,
                        }
                    )
                    occupied_groups[entry.group_name].append(slot)
                    if entry.teacher:
                        occupied_teachers[entry.teacher.name].append(slot)
                    if entry.room_id and entry.room_id in rooms:
                        occupied_rooms[entry.room_id].append(slot)

            priorities = settings.get("priorities", {})
            events: list[dict[str, Any]] = []
            group_sizes: dict[str, int] = {}
            unavailable = availability["unavailable"]
            for category, occupied in (
                ("teacher", occupied_teachers),
                ("group", occupied_groups),
                ("room", occupied_rooms),
            ):
                for resource, slots in occupied.items():
                    unavailable[category].setdefault(resource, []).extend(slots)
            for stream in streams:
                type_code = _activity_code(stream)
                if type_code is None:
                    continue
                groups = sorted(
                    {
                        group.group_name
                        for group in stream.groups
                        if group.group_name in selected_groups
                    }
                )
                if not groups:
                    continue
                for group in stream.groups:
                    if group.group_name in groups:
                        group_sizes[group.group_name] = max(
                            group_sizes.get(group.group_name, 0), group.group_size
                        )

                count = weekly_counts.get(stream.id, stream.lessons_count or 0)
                if count <= 0:
                    continue
                teacher_name = stream.teacher.name if stream.teacher else None
                if (
                    teacher_name
                    and teacher_name not in availability["structured_teacher_names"]
                ):
                    unavailable["teacher"].setdefault(teacher_name, []).extend(
                        _teacher_unavailable(stream, start_date, end_date)
                    )

                base_event = {
                    "stream_id": stream.id,
                    "subject": (
                        stream.discipline.full_name
                        if stream.discipline
                        else stream.event_name
                    ),
                    "stream_type": (
                        stream.activity_type.name
                        if stream.activity_type
                        else stream.stream_type or "Занятие"
                    ),
                    "type": type_code,
                    "teacher": teacher_name,
                    "teacher_id": stream.teacher_id,
                    "lessons_count": count,
                    "priority": weekly_priorities.get(stream.id, 5),
                    "time_preference": priorities.get(stream.event_name, "day"),
                    "required_room": (
                        stream.required_room.code if stream.required_room else None
                    ),
                    "required_features": [
                        requirement.feature.code
                        for requirement in stream.feature_requirements
                        if requirement.is_hard
                    ],
                }
                is_shared = type_code == "lec" or bool(
                    stream.activity_type and stream.activity_type.is_shared_for_groups
                )
                if is_shared:
                    event = {
                        **base_event,
                        "id": f"stream:{stream.id}",
                        "groups": groups,
                    }
                    if stream.id in fixed_by_stream:
                        event["fixed_slot"] = fixed_by_stream[stream.id]
                    events.append(event)
                else:
                    for group in groups:
                        event = {
                            **base_event,
                            "id": f"stream:{stream.id}:group:{group}",
                            "groups": [group],
                        }
                        fixed_slot = fixed_by_stream_group.get((stream.id, group))
                        if fixed_slot:
                            event["fixed_slot"] = fixed_slot
                        events.append(event)

            if not events:
                task.status = "failed"
                task.error_message = "No schedulable events found"
                await session.execute(
                    delete(GenerationLock).where(GenerationLock.task_id == task_id)
                )
                await session.commit()
                return None

            components = build_conflict_components(events)
            planning_dates = sum(
                1
                for offset in range(horizon_days)
                if (date.fromisoformat(start_date) + timedelta(days=offset)).weekday()
                in STUDY_DAYS
                and (
                    date.fromisoformat(start_date) + timedelta(days=offset)
                ).isoformat()
                not in holidays
            )
            estimated_decision_variables = len(events) * planning_dates * len(LESSONS)
            if estimated_decision_variables > MAX_ESTIMATED_DECISION_VARIABLES:
                task.status = "failed"
                task.progress_percent = 100
                task.error_message = (
                    "Generation model safety limit exceeded: "
                    f"estimated_decision_variables={estimated_decision_variables}/"
                    f"{MAX_ESTIMATED_DECISION_VARIABLES}. Split the calculation "
                    "by week or group set."
                )
                await session.execute(
                    delete(GenerationLock).where(GenerationLock.task_id == task_id)
                )
                await session.commit()
                return None
            max_total_events = max(
                1, min(int(settings.get("max_total_events", 20_000)), 20_000)
            )
            max_component_events = max(
                1, min(int(settings.get("max_component_events", 2_000)), 2_000)
            )
            largest_component = max(map(len, components))
            if (
                len(events) > max_total_events
                or largest_component > max_component_events
            ):
                task.status = "failed"
                task.progress_percent = 100
                task.error_message = (
                    "Generation safety limit exceeded: "
                    f"events={len(events)}/{max_total_events}, "
                    f"largest_component={largest_component}/{max_component_events}"
                )
                await session.execute(
                    delete(GenerationLock).where(GenerationLock.task_id == task_id)
                )
                await session.commit()
                return None
            max_component_seconds = int(
                settings.get("max_component_seconds", min(120, MAX_TIME_SECONDS))
            )
            max_component_seconds = max(5, min(max_component_seconds, MAX_TIME_SECONDS))
            solver_workers = max(
                1, min(int(settings.get("solver_workers", 1)), NUM_WORKERS)
            )
            room_assignment_max_seconds = max(
                1, min(int(settings.get("room_assignment_max_seconds", 5)), 60)
            )
            context = {
                "start_date": start_date,
                "end_date": end_date,
                "holidays": holidays,
                "study_days": STUDY_DAYS,
                "lessons": LESSONS,
                "rooms": rooms,
                "unavailable": unavailable,
                "preferred": availability["preferred"],
                "discouraged": availability["discouraged"],
                "rule_settings": rule_settings,
                "group_sizes": group_sizes,
                "max_time_seconds": max_component_seconds,
                "num_workers": solver_workers,
                "room_assignment_max_seconds": room_assignment_max_seconds,
                "immutable_before": (
                    max(
                        date.today(), datetime.fromisoformat(start_date).date()
                    ).isoformat()
                    if planning_week_id is not None
                    and (base_task_id or carry_over_entries)
                    else start_date
                ),
                "planning_week_id": planning_week_id,
                "base_task_id": int(base_task_id) if base_task_id else None,
                "carry_over_entries": carry_over_entries,
            }

            component_payloads = []
            for index, component_events in enumerate(components, start=1):
                component = GenerationComponent(
                    task_id=task_id,
                    component_key=f"component-{index:04d}",
                    event_count=len(component_events),
                )
                session.add(component)
                await session.flush()
                component_payloads.append(
                    {
                        "component_id": component.id,
                        "component_key": component.component_key,
                        "events": component_events,
                    }
                )

            task.total_components = len(component_payloads)
            task.metrics_json = json.dumps(
                {
                    "events": len(events),
                    "components": len(component_payloads),
                    "largest_component_events": largest_component,
                    "max_total_events": max_total_events,
                    "max_component_events": max_component_events,
                    "horizon_days": horizon_days,
                    "estimated_decision_variables": estimated_decision_variables,
                }
            )
            await session.commit()
            return {
                "task_id": task_id,
                "context": context,
                "components": component_payloads,
            }

    @staticmethod
    async def record_component_result(
        task_id: int, component_id: int, result: dict[str, Any]
    ) -> None:
        metrics = result.get("metrics", {})
        async with sessionmaker() as session:
            component = await session.get(GenerationComponent, component_id)
            if component is not None:
                component.status = result.get("status", "failed")
                component.variable_count = int(metrics.get("variables", 0))
                component.constraint_count = int(metrics.get("constraints", 0))
                component.solve_seconds = metrics.get("solve_seconds")
                component.objective = metrics.get("objective")
                component.error_message = result.get("error")
            await session.commit()

        async with sessionmaker() as session:
            completed = await session.scalar(
                select(func.count(GenerationComponent.id)).where(
                    GenerationComponent.task_id == task_id,
                    GenerationComponent.status.in_(("success", "failed")),
                )
            )
            task = await session.get(GenerationTask, task_id)
            if task is not None and task.status != "canceled":
                task.completed_components = int(completed or 0)
                task.progress_percent = min(
                    95,
                    int(task.completed_components * 90 / max(1, task.total_components))
                    + 5,
                )
                await session.commit()

    @staticmethod
    async def save_workflow_id(
        task_id: int, workflow_id: str, component_ids: list[str]
    ) -> None:
        async with sessionmaker() as session:
            await session.execute(
                update(GenerationTask)
                .where(
                    GenerationTask.id == task_id,
                    GenerationTask.status != "canceled",
                )
                .values(
                    celery_workflow_id=workflow_id,
                    celery_component_ids_json=json.dumps(component_ids),
                )
            )
            await session.commit()

    @staticmethod
    async def finalize(
        task_id: int,
        component_results: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> bool:
        successful_results = [
            result for result in component_results if result.get("status") == "success"
        ]
        assignments = [
            assignment
            for result in successful_results
            for assignment in result.get("assignments", [])
        ]
        unassigned = [
            item
            for result in successful_results
            for item in result.get("unassigned", [])
        ]
        room_assignments, room_warnings, room_metrics = assign_rooms_matching(
            assignments, context
        )

        async with sessionmaker() as session:
            task = await session.get(GenerationTask, task_id)
            if task is None:
                return False
            if task.status == "canceled":
                await session.execute(
                    delete(GenerationLock).where(GenerationLock.task_id == task_id)
                )
                await session.commit()
                return False
            await session.execute(
                delete(ScheduleEntry).where(ScheduleEntry.task_id == task_id)
            )
            await session.execute(
                delete(GenerationIssue).where(GenerationIssue.task_id == task_id)
            )

            entries: list[ScheduleEntry] = []
            for carried in context.get("carry_over_entries", []):
                entries.append(
                    ScheduleEntry(
                        task_id=task_id,
                        planning_week_id=context.get("planning_week_id"),
                        source_stream_id=carried["source_stream_id"],
                        group_name=carried["group_name"],
                        event_name=carried["event_name"],
                        stream_type=carried["stream_type"],
                        teacher_id=carried.get("teacher_id"),
                        room_id=carried.get("room_id"),
                        room_ref_id=carried.get("room_ref_id"),
                        date=datetime.fromisoformat(carried["date"]),
                        lesson_number=carried["lesson_number"],
                        warning=carried.get("warning"),
                        is_locked=bool(carried.get("is_locked")),
                    )
                )
            for assignment in room_assignments:
                slot_date = datetime.fromisoformat(assignment["slot"][0])
                for group in assignment["groups"]:
                    entries.append(
                        ScheduleEntry(
                            task_id=task_id,
                            planning_week_id=context.get("planning_week_id"),
                            source_stream_id=assignment["stream_id"],
                            group_name=group,
                            event_name=assignment["subject"],
                            stream_type=assignment["stream_type"],
                            teacher_id=assignment.get("teacher_id"),
                            room_id=assignment["room"],
                            room_ref_id=assignment.get("room_ref_id"),
                            date=slot_date,
                            lesson_number=int(assignment["slot"][1]),
                            warning=assignment.get("warning"),
                            is_locked=bool(assignment.get("fixed_slot")),
                        )
                    )

            for item in unassigned:
                for group in item["groups"]:
                    for _ in range(int(item["missing_count"])):
                        entries.append(
                            ScheduleEntry(
                                task_id=task_id,
                                planning_week_id=context.get("planning_week_id"),
                                source_stream_id=item["stream_id"],
                                group_name=group,
                                event_name=item["subject"],
                                stream_type=item["stream_type"],
                                teacher_id=item.get("teacher_id"),
                                warning=(
                                    f"Не выставлено {item['missing_count']} из "
                                    f"{item['target']} занятий"
                                ),
                            )
                        )
            session.add_all(entries)

            failed_results = [
                result
                for result in component_results
                if result.get("status") != "success"
            ]
            issues: list[GenerationIssue] = []
            for item in unassigned:
                for group in item["groups"]:
                    issues.append(
                        GenerationIssue(
                            task_id=task_id,
                            kind="unassigned",
                            severity="error",
                            message=(
                                f"Не размещено {item['missing_count']} из "
                                f"{item['target']} занятий"
                            ),
                            stream_id=item.get("stream_id"),
                            group_name=group,
                            details_json=json.dumps(
                                {
                                    "subject": item.get("subject"),
                                    "teacher": item.get("teacher"),
                                }
                            ),
                        )
                    )
            assignments_by_id = {item["id"]: item for item in assignments}
            for warning in room_warnings:
                assignment = assignments_by_id.get(warning["event_id"], {})
                issues.append(
                    GenerationIssue(
                        task_id=task_id,
                        kind="room",
                        severity="warning",
                        message=warning["message"],
                        stream_id=assignment.get("stream_id"),
                        group_name=", ".join(assignment.get("groups", [])) or None,
                        date=date.fromisoformat(warning["date"]),
                        lesson_number=warning["lesson"],
                    )
                )
            for result in failed_results:
                issues.append(
                    GenerationIssue(
                        task_id=task_id,
                        kind="component",
                        severity="error",
                        message=result.get("error") or "Компонента не рассчитана",
                        details_json=json.dumps(result.get("metrics", {})),
                    )
                )
            session.add_all(issues)
            component_metrics = [
                result.get("metrics", {}) for result in component_results
            ]
            task.metrics_json = json.dumps(
                {
                    "events": sum(
                        int(metrics.get("events", 0)) for metrics in component_metrics
                    ),
                    "components": len(component_results),
                    "variables": sum(
                        int(metrics.get("variables", 0))
                        for metrics in component_metrics
                    ),
                    "constraints": sum(
                        int(metrics.get("constraints", 0))
                        for metrics in component_metrics
                    ),
                    "component_solve_seconds": sum(
                        float(metrics.get("solve_seconds", 0) or 0)
                        for metrics in component_metrics
                    ),
                    "room_assignment": room_metrics,
                    "room_warning_count": len(room_warnings),
                    "unassigned_count": sum(
                        int(item["missing_count"]) for item in unassigned
                    ),
                }
            )
            task.result_count = len(entries)
            task.completed_components = task.total_components
            task.progress_percent = 100
            if failed_results and entries:
                task.status = "partial"
                task.error_message = "; ".join(
                    result.get("error") or "Component failed"
                    for result in failed_results
                )
            elif failed_results:
                task.status = "failed"
                task.error_message = "; ".join(
                    result.get("error") or "Component failed"
                    for result in failed_results
                )
            else:
                task.status = "success"
                task.error_message = None
            await session.execute(
                delete(GenerationLock).where(GenerationLock.task_id == task_id)
            )
            await session.commit()
            return task.status in {"success", "partial"}

    @staticmethod
    async def fail(task_id: int, error: str) -> None:
        async with sessionmaker() as session:
            await session.execute(
                update(GenerationTask)
                .where(GenerationTask.id == task_id)
                .values(status="failed", error_message=error, progress_percent=100)
            )
            await session.execute(
                delete(GenerationLock).where(GenerationLock.task_id == task_id)
            )
            await session.commit()
