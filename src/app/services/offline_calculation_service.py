from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from database import (
    GenerationComponent,
    GenerationTask,
    OfflineCalculation,
    PlanningWeek,
    Room,
    Stream,
    Teacher,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.calculation_package import (
    PackageValidationError,
    canonical_json_bytes,
    create_result_archive,
    create_task_archive,
    payload_sha256,
    read_result_archive,
)
from services.generation_lifecycle_service import GenerationLifecycleService
from services.scalable_generation_service import ScalableGenerationService

NO_ROOM = "НЕТ АУДИТОРИИ"


@dataclass(frozen=True)
class OfflineTaskSpec:
    groups: list[str]
    holidays: list[str]
    settings: dict[str, Any]
    planning_week_id: int | None
    start_date: datetime | None
    end_date: datetime | None
    semester_batch_id: str | None = None


class OfflineCalculationService:
    @classmethod
    async def create_task_package(
        cls, specs: list[OfflineTaskSpec], db: AsyncSession
    ) -> tuple[Any, list[int]]:
        if not specs:
            raise PackageValidationError("At least one calculation is required")

        payloads: list[dict[str, Any]] = []
        task_ids: list[int] = []
        created_task_ids: list[int] = []
        try:
            for spec in specs:
                payload, task_id = await cls._prepare_task(spec, db, created_task_ids)
                payloads.append(payload)
                task_ids.append(task_id)
        except Exception:
            await db.rollback()
            if created_task_ids:
                await db.execute(
                    delete(GenerationTask).where(
                        GenerationTask.id.in_(created_task_ids)
                    )
                )
                await db.commit()
            raise

        return create_task_archive(payloads), task_ids

    @staticmethod
    async def _prepare_task(
        spec: OfflineTaskSpec,
        db: AsyncSession,
        created_task_ids: list[int],
    ) -> tuple[dict[str, Any], int]:
        task = await GenerationLifecycleService.reserve_task(
            db,
            groups=spec.groups,
            holidays=spec.holidays,
            settings=spec.settings,
            planning_week_id=spec.planning_week_id,
            start_date=spec.start_date,
            end_date=spec.end_date,
            semester_batch_id=spec.semester_batch_id,
        )
        task_id = task.id
        created_task_ids.append(task_id)
        prepared = await ScalableGenerationService.prepare(
            task_id,
            spec.groups,
            spec.holidays,
            spec.settings.get("enabled_types", []),
            spec.start_date.date().isoformat() if spec.start_date else None,
            spec.end_date.date().isoformat() if spec.end_date else None,
            spec.planning_week_id,
        )
        db.expire_all()
        task = await db.get(GenerationTask, task_id)
        if prepared is None or task is None:
            raise PackageValidationError(
                "Unable to prepare one of the offline calculations"
            )
        if task.status == "failed":
            raise PackageValidationError(
                task.error_message or "Unable to prepare offline calculation"
            )

        job_uuid = str(uuid.uuid4())
        payload = {
            "job_uuid": job_uuid,
            "context": prepared["context"],
            "components": [
                {
                    "component_key": component["component_key"],
                    "events": component["events"],
                }
                for component in prepared["components"]
            ],
        }
        digest = payload_sha256(payload)
        db.add(
            OfflineCalculation(
                task_id=task_id,
                job_uuid=job_uuid,
                schema_version=1,
                input_sha256=digest,
                input_payload_json=canonical_json_bytes(payload).decode("utf-8"),
            )
        )
        task.status = "awaiting_result"
        task.progress_percent = 0
        task.completed_components = 0
        task.error_message = None
        await GenerationLifecycleService.release_locks(task_id, db)
        await db.commit()
        return payload, task_id

    @staticmethod
    async def get_task_package(task_id: int, db: AsyncSession) -> Any:
        record = await db.scalar(
            select(OfflineCalculation).where(OfflineCalculation.task_id == task_id)
        )
        if record is None:
            raise LookupError("Offline calculation not found")
        payload = _load_stored_payload(record.input_payload_json)
        if payload_sha256(payload) != record.input_sha256:
            raise PackageValidationError("Stored task payload is corrupted")
        return create_task_archive([payload])

    @staticmethod
    async def get_result_package(task_id: int, db: AsyncSession) -> Any:
        record = await db.scalar(
            select(OfflineCalculation).where(OfflineCalculation.task_id == task_id)
        )
        if record is None or not record.result_payload_json:
            raise LookupError("Offline result not found")
        payload = _load_stored_payload(record.result_payload_json)
        return create_result_archive([payload])

    @classmethod
    async def import_result_package(
        cls, content: bytes, db: AsyncSession
    ) -> list[dict[str, Any]]:
        _manifest, result_jobs = read_result_archive(content)
        job_uuids = [job["job_uuid"] for job in result_jobs]
        records = list(
            (
                await db.execute(
                    select(OfflineCalculation)
                    .where(OfflineCalculation.job_uuid.in_(job_uuids))
                    .options(selectinload(OfflineCalculation.task))
                )
            ).scalars()
        )
        records_by_uuid = {record.job_uuid: record for record in records}
        if set(records_by_uuid) != set(job_uuids):
            raise LookupError("Result contains an unknown offline calculation")

        validated: list[
            tuple[
                int,
                int,
                dict[str, Any],
                dict[str, Any],
                list[dict[str, Any]],
                tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]],
            ]
        ] = []
        for result_job in result_jobs:
            record = records_by_uuid[result_job["job_uuid"]]
            if result_job.get("input_sha256") != record.input_sha256:
                raise PackageValidationError(
                    "Result was produced for a different task snapshot"
                )
            if record.task.publication_status != "draft":
                raise PackageValidationError(
                    "Published or archived schedules cannot be replaced"
                )
            if record.task.status == "success" and record.result_payload_json:
                raise PackageValidationError(
                    "This offline calculation already has a completed result"
                )
            input_payload = _load_stored_payload(record.input_payload_json)
            if payload_sha256(input_payload) != record.input_sha256:
                raise PackageValidationError("Stored task payload is corrupted")
            component_results = _validate_component_results(input_payload, result_job)
            room_solution = _validate_room_solution(
                input_payload["context"], component_results, result_job
            )
            await _validate_database_references(
                input_payload, component_results, room_solution, db
            )
            normalized_job = {
                "job_uuid": record.job_uuid,
                "input_sha256": record.input_sha256,
                "component_results": [
                    {
                        "component_key": component["component_key"],
                        "result": result,
                    }
                    for component, result in zip(
                        input_payload["components"], component_results
                    )
                ],
                "room_assignments": room_solution[0],
                "room_warnings": room_solution[1],
                "room_metrics": room_solution[2],
                "solver": _safe_metadata(result_job.get("solver", {})),
            }
            validated.append(
                (
                    record.id,
                    record.task_id,
                    input_payload,
                    normalized_job,
                    component_results,
                    room_solution,
                )
            )

        imported: list[dict[str, Any]] = []
        for (
            record_id,
            task_id,
            stored_payload,
            normalized_job,
            component_results,
            room_solution,
        ) in validated:
            component_rows = list(
                (
                    await db.execute(
                        select(GenerationComponent).where(
                            GenerationComponent.task_id == task_id
                        )
                    )
                ).scalars()
            )
            rows_by_key = {row.component_key: row for row in component_rows}
            for item, result in zip(
                stored_payload["components"],
                component_results,
            ):
                row = rows_by_key.get(item["component_key"])
                if row is None:
                    raise PackageValidationError(
                        "Stored calculation component is missing"
                    )
                await ScalableGenerationService.record_component_result(
                    task_id, row.id, result
                )

            task = await db.get(GenerationTask, task_id)
            if task is None:
                raise RuntimeError("Offline task disappeared during import")
            task.status = "importing"
            await db.commit()
            finalized = await ScalableGenerationService.finalize(
                task_id,
                component_results,
                stored_payload["context"],
                room_solution=room_solution,
            )
            db.expire_all()
            refreshed_record = await db.scalar(
                select(OfflineCalculation)
                .where(OfflineCalculation.id == record_id)
                .options(selectinload(OfflineCalculation.task))
            )
            if refreshed_record is None:
                raise RuntimeError("Offline calculation disappeared during import")
            refreshed_record.result_payload_json = canonical_json_bytes(
                normalized_job
            ).decode("utf-8")
            refreshed_record.imported_at = datetime.now(timezone.utc).replace(
                tzinfo=None
            )
            await db.commit()
            imported.append(
                {
                    "task_id": refreshed_record.task_id,
                    "status": refreshed_record.task.status,
                    "accepted": finalized
                    or refreshed_record.task.status in {"failed", "partial"},
                }
            )
        return imported


def _load_stored_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PackageValidationError("Stored calculation payload is invalid") from exc
    if not isinstance(payload, dict):
        raise PackageValidationError("Stored calculation payload is invalid")
    return payload


def _safe_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or len(key) > 100:
            continue
        if isinstance(item, str):
            safe[key] = item[:500]
        elif isinstance(item, bool) or item is None:
            safe[key] = item
        elif isinstance(item, int):
            safe[key] = max(-(10**12), min(10**12, item))
        elif isinstance(item, float) and math.isfinite(item):
            safe[key] = item
    return safe


def _validate_component_results(
    input_payload: dict[str, Any], result_job: dict[str, Any]
) -> list[dict[str, Any]]:
    components = input_payload.get("components")
    raw_results = result_job.get("component_results")
    if not isinstance(components, list) or not isinstance(raw_results, list):
        raise PackageValidationError("Result component list is invalid")
    expected_by_key = {
        component.get("component_key"): component for component in components
    }
    if None in expected_by_key or len(expected_by_key) != len(components):
        raise PackageValidationError("Stored component list is invalid")
    provided_by_key: dict[str, Any] = {}
    for item in raw_results:
        if not isinstance(item, dict) or not isinstance(item.get("component_key"), str):
            raise PackageValidationError("Result component descriptor is invalid")
        key = item["component_key"]
        if key in provided_by_key:
            raise PackageValidationError("Result contains duplicate components")
        provided_by_key[key] = item.get("result")
    if set(provided_by_key) != set(expected_by_key):
        raise PackageValidationError("Result component set does not match the task")

    normalized: list[dict[str, Any]] = []
    all_assignments: list[dict[str, Any]] = []
    context = input_payload.get("context")
    if not isinstance(context, dict):
        raise PackageValidationError("Stored calculation context is invalid")
    for component in components:
        result = _normalize_component_result(
            component, provided_by_key[component["component_key"]], context
        )
        normalized.append(result)
        all_assignments.extend(result.get("assignments", []))
    _validate_resource_conflicts(all_assignments)
    return normalized


def _normalize_component_result(
    component: dict[str, Any], raw_result: Any, context: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(raw_result, dict):
        raise PackageValidationError("Component result must be an object")
    status = raw_result.get("status")
    if status not in {"success", "failed"}:
        raise PackageValidationError("Component result has an invalid status")
    raw_assignments = raw_result.get("assignments")
    raw_unassigned = raw_result.get("unassigned")
    if not isinstance(raw_assignments, list) or not isinstance(raw_unassigned, list):
        raise PackageValidationError("Component assignments are invalid")
    events = component.get("events")
    if not isinstance(events, list):
        raise PackageValidationError("Stored component events are invalid")
    events_by_id = {
        event.get("id"): event for event in events if isinstance(event, dict)
    }
    if None in events_by_id or len(events_by_id) != len(events):
        raise PackageValidationError("Stored component contains invalid event IDs")

    error = raw_result.get("error")
    if error is not None and not isinstance(error, str):
        raise PackageValidationError("Component error must be text")
    if status == "failed":
        if raw_assignments or raw_unassigned:
            raise PackageValidationError("Failed component must not contain a schedule")
        return {
            "status": "failed",
            "assignments": [],
            "unassigned": [],
            "error": (error or "Local solver failed")[:2000],
            "metrics": _safe_metadata(raw_result.get("metrics", {})),
        }

    normalized_assignments: list[dict[str, Any]] = []
    assignment_counts = {event_id: 0 for event_id in events_by_id}
    event_days: set[tuple[str, str]] = set()
    event_slots: set[tuple[str, str, int]] = set()
    for assignment in raw_assignments:
        if not isinstance(assignment, dict):
            raise PackageValidationError("Assignment must be an object")
        event_id = assignment.get("id")
        event = events_by_id.get(event_id)
        if event is None:
            raise PackageValidationError("Result contains an unknown event")
        slot = _normalize_slot(assignment.get("slot"), event, context)
        event_slot = (str(event_id), slot[0], slot[1])
        event_day = (str(event_id), slot[0])
        if event_slot in event_slots or event_day in event_days:
            raise PackageValidationError("An event is scheduled more than once per day")
        event_slots.add(event_slot)
        event_days.add(event_day)
        assignment_counts[event_id] += 1
        normalized_assignments.append({**event, "slot": slot})

    missing_counts = {event_id: 0 for event_id in events_by_id}
    normalized_unassigned: list[dict[str, Any]] = []
    for item in raw_unassigned:
        if not isinstance(item, dict):
            raise PackageValidationError("Unassigned event must be an object")
        event_id = item.get("id")
        event = events_by_id.get(event_id)
        if event is None or missing_counts[event_id]:
            raise PackageValidationError("Unassigned event is unknown or duplicated")
        missing = item.get("missing_count")
        target = int(event.get("lessons_count", 0))
        if not isinstance(missing, int) or isinstance(missing, bool):
            raise PackageValidationError("Missing lesson count must be an integer")
        if not 1 <= missing <= target:
            raise PackageValidationError("Missing lesson count is out of range")
        missing_counts[event_id] = missing
        normalized_unassigned.append(
            {**event, "missing_count": missing, "target": target}
        )

    for event_id, event in events_by_id.items():
        target = int(event.get("lessons_count", 0))
        if assignment_counts[event_id] + missing_counts[event_id] != target:
            raise PackageValidationError(
                "Result does not account for every requested lesson"
            )
    return {
        "status": "success",
        "assignments": normalized_assignments,
        "unassigned": normalized_unassigned,
        "error": None,
        "metrics": _safe_metadata(raw_result.get("metrics", {})),
    }


def _normalize_slot(
    raw_slot: Any, event: dict[str, Any], context: dict[str, Any]
) -> list[Any]:
    if not isinstance(raw_slot, list) or len(raw_slot) != 2:
        raise PackageValidationError("Assignment slot is invalid")
    date_string, lesson = raw_slot
    if (
        not isinstance(date_string, str)
        or not isinstance(lesson, int)
        or isinstance(lesson, bool)
    ):
        raise PackageValidationError("Assignment slot has invalid values")
    try:
        slot_date = date.fromisoformat(date_string)
        start_date = date.fromisoformat(context["start_date"])
        end_date = date.fromisoformat(context["end_date"])
        immutable_before = date.fromisoformat(
            context.get("immutable_before", context["start_date"])
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageValidationError("Calculation contains invalid dates") from exc
    if not max(start_date, immutable_before) <= slot_date <= end_date:
        raise PackageValidationError("Assignment date is outside the task horizon")
    if slot_date.weekday() not in set(context.get("study_days", [])):
        raise PackageValidationError("Assignment is placed on a non-study day")
    if date_string in set(context.get("holidays", [])):
        raise PackageValidationError("Assignment is placed on a holiday")
    if lesson not in set(context.get("lessons", [])):
        raise PackageValidationError("Assignment lesson number is invalid")
    fixed_slot = event.get("fixed_slot")
    if fixed_slot and [date_string, lesson] != fixed_slot:
        raise PackageValidationError("Fixed event was moved by the imported result")
    if _resource_is_unavailable(event, date_string, lesson, context):
        raise PackageValidationError("Assignment violates resource availability")
    return [date_string, lesson]


def _resource_is_unavailable(
    event: dict[str, Any], date_string: str, lesson: int, context: dict[str, Any]
) -> bool:
    unavailable = context.get("unavailable", {})
    slot_date = date.fromisoformat(date_string)
    candidates = [("global", "*"), ("teacher", event.get("teacher"))]
    candidates.extend(("group", group) for group in event.get("groups", []))
    for category, resource in candidates:
        if resource is None:
            continue
        raw_slots = unavailable.get(category, {}).get(str(resource), [])
        for raw_slot in raw_slots:
            if not isinstance(raw_slot, list) or len(raw_slot) != 2:
                continue
            day, raw_lesson = raw_slot
            if int(raw_lesson) != lesson:
                continue
            if day == date_string or day == slot_date.weekday():
                return True
    return False


def _validate_resource_conflicts(assignments: list[dict[str, Any]]) -> None:
    group_slots: set[tuple[str, str, int]] = set()
    teacher_slots: set[tuple[str, str, int]] = set()
    for assignment in assignments:
        date_string, lesson = assignment["slot"]
        for group in assignment.get("groups", []):
            key = (str(group), date_string, lesson)
            if key in group_slots:
                raise PackageValidationError("Imported result has a group conflict")
            group_slots.add(key)
        teacher = assignment.get("teacher_id") or assignment.get("teacher")
        if teacher:
            key = (str(teacher), date_string, lesson)
            if key in teacher_slots:
                raise PackageValidationError("Imported result has a teacher conflict")
            teacher_slots.add(key)


def _validate_room_solution(
    context: dict[str, Any],
    component_results: list[dict[str, Any]],
    result_job: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    expected_assignments = [
        assignment
        for result in component_results
        if result["status"] == "success"
        for assignment in result["assignments"]
    ]
    expected_by_slot = {
        (assignment["id"], assignment["slot"][0], assignment["slot"][1]): assignment
        for assignment in expected_assignments
    }
    raw_rooms = result_job.get("room_assignments")
    if not isinstance(raw_rooms, list) or len(raw_rooms) != len(expected_assignments):
        raise PackageValidationError("Room assignment set does not match the schedule")
    rooms = context.get("rooms")
    if not isinstance(rooms, dict):
        raise PackageValidationError("Stored room context is invalid")
    completed: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_events: set[tuple[Any, str, int]] = set()
    occupied_rooms: set[tuple[str, str, int]] = set()
    for raw in raw_rooms:
        if not isinstance(raw, dict):
            raise PackageValidationError("Room assignment is invalid")
        slot = raw.get("slot")
        if not isinstance(slot, list) or len(slot) != 2:
            raise PackageValidationError("Room assignment slot is invalid")
        key = (raw.get("id"), slot[0], slot[1])
        expected = expected_by_slot.get(key)
        if expected is None or key in seen_events:
            raise PackageValidationError("Room assignment references an unknown event")
        seen_events.add(key)
        room_name = raw.get("room")
        if not isinstance(room_name, str) or len(room_name) > 100:
            raise PackageValidationError("Room code is invalid")
        warning: str | None = None
        room_ref_id = None
        if room_name == NO_ROOM:
            warning = "Не хватило аудиторий"
        else:
            room = rooms.get(room_name)
            if not isinstance(room, dict):
                raise PackageValidationError("Result contains an unknown room")
            room_slot = (room_name, str(slot[0]), int(slot[1]))
            if room_slot in occupied_rooms:
                raise PackageValidationError("Imported result has a room conflict")
            occupied_rooms.add(room_slot)
            if _room_is_unavailable(room_name, str(slot[0]), int(slot[1]), context):
                raise PackageValidationError("Imported room is unavailable")
            required_room = expected.get("required_room")
            if required_room not in {None, room_name}:
                raise PackageValidationError("Required room constraint was violated")
            size = sum(
                int(context.get("group_sizes", {}).get(group, 20))
                for group in expected.get("groups", [])
            )
            capacity_shortfall = int(room.get("capacity", 0)) < size
            type_mismatch = room.get("type") not in {
                None,
                "mixed",
                expected.get("type"),
            }
            missing_features = set(expected.get("required_features", [])) - set(
                room.get("features", [])
            )
            if _hard_rule(context, "room_capacity") and capacity_shortfall:
                raise PackageValidationError(
                    "Hard room capacity constraint was violated"
                )
            if _hard_rule(context, "room_type") and type_mismatch:
                raise PackageValidationError("Hard room type constraint was violated")
            if _hard_rule(context, "room_features") and missing_features:
                raise PackageValidationError(
                    "Hard room feature constraint was violated"
                )
            if capacity_shortfall:
                warning = f"Вместимость: {room.get('capacity', 0)} на {size} чел."
            elif type_mismatch:
                warning = f"Тип: {room.get('type')} вместо {expected.get('type')}"
            elif missing_features:
                warning = "Нет оснащения: " + ", ".join(sorted(missing_features))
            room_ref_id = room.get("id")
        completed_assignment = {
            **expected,
            "room": room_name,
            "room_ref_id": room_ref_id,
            "warning": warning,
        }
        completed.append(completed_assignment)
        if warning:
            warnings.append(
                {
                    "event_id": expected["id"],
                    "date": str(slot[0]),
                    "lesson": int(slot[1]),
                    "message": warning,
                }
            )
    if len(seen_events) != len(expected_by_slot):
        raise PackageValidationError("Some events have no room assignment")
    return completed, warnings, _safe_metadata(result_job.get("room_metrics", {}))


def _room_is_unavailable(
    room_name: str, date_string: str, lesson: int, context: dict[str, Any]
) -> bool:
    raw_slots = context.get("unavailable", {}).get("room", {}).get(room_name, [])
    weekday = date.fromisoformat(date_string).weekday()
    for raw_slot in raw_slots:
        if not isinstance(raw_slot, list) or len(raw_slot) != 2:
            continue
        day, raw_lesson = raw_slot
        if int(raw_lesson) == lesson and day in {date_string, weekday}:
            return True
    return False


def _hard_rule(context: dict[str, Any], code: str) -> bool:
    configured = context.get("rule_settings", {}).get(code, {})
    return bool(configured.get("enabled", True) and configured.get("is_hard", False))


async def _validate_database_references(
    input_payload: dict[str, Any],
    component_results: list[dict[str, Any]],
    room_solution: tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]],
    db: AsyncSession,
) -> None:
    context = input_payload["context"]
    carried = context.get("carry_over_entries", [])
    scheduled = room_solution[0]
    unassigned = [
        item
        for result in component_results
        if result["status"] == "success"
        for item in result["unassigned"]
    ]
    all_entries = [*scheduled, *unassigned, *carried]
    stream_ids = {
        int(item.get("stream_id", item.get("source_stream_id")))
        for item in all_entries
        if item.get("stream_id", item.get("source_stream_id")) is not None
    }
    teacher_ids = {
        int(item["teacher_id"])
        for item in all_entries
        if item.get("teacher_id") is not None
    }
    room_ids = {
        int(item["room_ref_id"])
        for item in [*scheduled, *carried]
        if item.get("room_ref_id") is not None
    }
    planning_week_id = context.get("planning_week_id")

    checks = (
        (Stream, stream_ids, "streams"),
        (Teacher, teacher_ids, "teachers"),
        (Room, room_ids, "rooms"),
    )
    for model, expected_ids, label in checks:
        if not expected_ids:
            continue
        existing_ids = set(
            (
                await db.execute(select(model.id).where(model.id.in_(expected_ids)))
            ).scalars()
        )
        if existing_ids != expected_ids:
            raise PackageValidationError(
                f"Reference data changed after export: missing {label}"
            )
    if (
        planning_week_id is not None
        and await db.get(PlanningWeek, int(planning_week_id)) is None
    ):
        raise PackageValidationError(
            "Reference data changed after export: planning week is missing"
        )
