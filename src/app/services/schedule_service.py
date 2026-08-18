import json
import logging
from typing import Any, Dict, List

import pandas as pd
from database.all_models import (
    AvailabilityRule,
    Room,
    ScheduleEntry,
    Stream,
    StreamGroup,
    StudentGroup,
    Teacher,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.availability_service import build_availability_context

logger = logging.getLogger(__name__)
NO_ROOM_VALUES = {"НЕТ АУДИТОРИИ", "NO ROOM"}


def _is_real_room_code(room_code: str | None) -> bool:
    return bool(room_code and room_code.strip().upper() not in NO_ROOM_VALUES)


class ScheduleService:
    @classmethod
    async def validate_manual_changes(
        cls,
        task_id: int,
        changed_ids: set[int],
        db: AsyncSession,
    ) -> list[str]:
        stmt = (
            select(ScheduleEntry)
            .options(selectinload(ScheduleEntry.teacher))
            .where(ScheduleEntry.task_id == task_id)
            .execution_options(populate_existing=True)
        )
        entries = list((await db.execute(stmt)).scalars())
        changed = [entry for entry in entries if entry.id in changed_ids]
        errors: set[str] = set()
        for entry in changed:
            if entry.date is None or entry.lesson_number is None:
                continue
            for other in entries:
                if other.id == entry.id or other.date != entry.date:
                    continue
                if other.lesson_number != entry.lesson_number:
                    continue
                same_stream = bool(
                    entry.source_stream_id
                    and entry.source_stream_id == other.source_stream_id
                )
                if entry.group_name == other.group_name and not same_stream:
                    errors.add(
                        f"Группа {entry.group_name} уже занята: {other.event_name}"
                    )
                if (
                    entry.teacher_id
                    and entry.teacher_id == other.teacher_id
                    and not same_stream
                ):
                    errors.add(
                        f"Преподаватель уже занят: {other.event_name} "
                        f"({other.group_name})"
                    )
                if (
                    _is_real_room_code(entry.room_id)
                    and entry.room_id == other.room_id
                    and not same_stream
                ):
                    errors.add(
                        f"Аудитория {entry.room_id} уже занята: {other.event_name}"
                    )

            date_string = entry.date.date().isoformat()
            availability = await build_availability_context(
                db, date_string, date_string
            )
            slot = [date_string, entry.lesson_number]
            unavailable = availability["unavailable"]
            if slot in unavailable.get("global", {}).get("*", []):
                errors.add("Выбранный слот недоступен для университета")
            if entry.teacher and slot in unavailable.get("teacher", {}).get(
                entry.teacher.name, []
            ):
                errors.add(f"Преподаватель {entry.teacher.name} недоступен")
            if slot in unavailable.get("group", {}).get(entry.group_name, []):
                errors.add(f"Группа {entry.group_name} недоступна")
            if _is_real_room_code(entry.room_id) and slot in unavailable.get(
                "room", {}
            ).get(
                entry.room_id, []
            ):
                errors.add(f"Аудитория {entry.room_id} недоступна")
        return sorted(errors)

    @staticmethod
    async def resolve_room(room_code: str | None, db: AsyncSession) -> Room | None:
        if room_code is None:
            return None
        room = await db.scalar(
            select(Room).where(Room.code == room_code, Room.is_active.is_(True))
        )
        if room is None:
            raise LookupError(f"Активная аудитория {room_code} не найдена")
        return room

    @classmethod
    async def refresh_task_warnings(cls, task_id: int, db: AsyncSession) -> None:
        stmt = (
            select(ScheduleEntry)
            .options(selectinload(ScheduleEntry.teacher))
            .where(ScheduleEntry.task_id == task_id)
        )
        res = await db.execute(stmt)
        all_entries = res.scalars().all()

        by_slot: Dict[tuple[str, int], List[ScheduleEntry]] = {}
        lessons_by_group_day: Dict[tuple[str, str], set[int]] = {}
        for e in all_entries:
            if e.date and e.lesson_number:
                date_key = (
                    e.date.strftime("%Y-%m-%d")
                    if hasattr(e.date, "strftime")
                    else str(e.date)
                )
                key = (date_key, e.lesson_number)
                if key not in by_slot:
                    by_slot[key] = []
                by_slot[key].append(e)
                lessons_by_group_day.setdefault(
                    (e.group_name, date_key), set()
                ).add(e.lesson_number)
            else:
                e.warning = None

        lunch_violations = {
            key
            for key, lesson_numbers in lessons_by_group_day.items()
            if {3, 4}.issubset(lesson_numbers)
        }

        for (_d, _l), slot_entries in by_slot.items():
            for e1 in slot_entries:
                slot_warnings: List[str] = []

                # 1. Overlap checks
                for e2 in slot_entries:
                    if e1.id == e2.id:
                        continue
                    same_stream = bool(
                        e1.source_stream_id
                        and e1.source_stream_id == e2.source_stream_id
                    )

                    # Shared stream rows represent one lesson for several groups.
                    if (
                        e1.teacher_id
                        and e1.teacher_id == e2.teacher_id
                        and not same_stream
                    ):
                        slot_warnings.append(
                            f"Преподаватель занят: {e2.event_name} ({e2.group_name})"
                        )

                    # Same group = real conflict
                    if e1.group_name == e2.group_name:
                        slot_warnings.append(
                            f"У группы {e1.group_name} уже есть пара ({e2.event_name})"
                        )

                    if (
                        _is_real_room_code(e1.room_id)
                        and e1.room_id == e2.room_id
                        and not same_stream
                    ):
                        slot_warnings.append(
                            f"Аудитория занята: {e2.event_name} ({e2.group_name})"
                        )

                if (
                    e1.lesson_number in {3, 4}
                    and (e1.group_name, _d) in lunch_violations
                ):
                    slot_warnings.append(
                        "Заняты 3-я и 4-я пары — нет свободного окна для обеда"
                    )

                # 2. Personal Teacher Availability
                if e1.teacher and e1.teacher.restrictions_json:
                    try:
                        restrs = json.loads(e1.teacher.restrictions_json)
                        if not isinstance(restrs, dict):
                            restrs = {
                                "mode": "blacklist",
                                "recurring": restrs,
                                "specific": [],
                            }

                        mode = restrs.get("mode", "blacklist")
                        recurring = restrs.get("recurring", [])
                        specific = restrs.get("specific", [])

                        # Frontend uses JS Date.getDay(): 0=Sun, 1=Mon, ..., 6=Sat
                        # Python weekday(): 0=Mon, ..., 6=Sun
                        # Convert Python weekday to JS getDay: (weekday + 1) % 7
                        py_wd = e1.date.weekday() if hasattr(e1.date, "weekday") else -1
                        js_weekday = (py_wd + 1) % 7 if py_wd >= 0 else -1
                        lesson = e1.lesson_number
                        date_str = (
                            e1.date.strftime("%Y-%m-%d")
                            if hasattr(e1.date, "strftime")
                            else str(e1.date)
                        )

                        # Check recurring: format is "WEEKDAY-LESSON" e.g. "1-3"
                        is_in_recurring = False
                        for item in recurring:
                            item_str = str(item)
                            for sep in ["-", "_", ":"]:
                                if sep in item_str:
                                    try:
                                        d_s, l_s = item_str.split(sep, 1)
                                        if (
                                            int(d_s) == js_weekday
                                            and int(l_s) == lesson
                                        ):
                                            is_in_recurring = True
                                            break
                                    except (TypeError, ValueError):
                                        continue
                            if is_in_recurring:
                                break

                        # Check specific: format is "YYYY-MM-DD-LESSON" e.g. "2026-05-16-3"
                        is_in_specific = False
                        for item in specific:
                            item_str = str(item)
                            if len(item_str) > 10:
                                for sep in ["-", "_", ":"]:
                                    try:
                                        parts = item_str.rsplit(sep, 1)
                                        if (
                                            len(parts) == 2
                                            and parts[0] == date_str
                                            and int(parts[1]) == lesson
                                        ):
                                            is_in_specific = True
                                            break
                                    except (TypeError, ValueError):
                                        continue
                            if is_in_specific:
                                break

                        is_blocked = False
                        if mode == "whitelist":
                            if not is_in_recurring and not is_in_specific:
                                is_blocked = True
                        else:  # blacklist
                            if is_in_recurring or is_in_specific:
                                is_blocked = True

                        if is_blocked:
                            slot_warnings.append(
                                "Преподаватель недоступен по личному расписанию"
                            )
                    except Exception as ex:
                        logger.error(
                            f"Error parsing restrictions for teacher "
                            f"{e1.teacher.name}: {ex}"
                        )

                e1.warning = "; ".join(slot_warnings) if slot_warnings else None

    @classmethod
    async def get_task_entries_json(
        cls, task_id: int, db: AsyncSession
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(ScheduleEntry)
            .options(selectinload(ScheduleEntry.teacher))
            .where(ScheduleEntry.task_id == task_id)
        )
        result = await db.execute(stmt)
        entries = result.scalars().all()
        return [
            {
                "id": e.id,
                "task_id": e.task_id,
                "group_name": e.group_name,
                "event_name": e.event_name,
                "stream_type": e.stream_type,
                "teacher": e.teacher.name if e.teacher else None,
                "teacher_id": e.teacher_id,
                "room_id": e.room_id,
                "date": e.date.strftime("%Y-%m-%d") if e.date else None,
                "lesson_number": e.lesson_number,
                "warning": e.warning,
                "is_locked": e.is_locked,
            }
            for e in entries
        ]

    @classmethod
    async def import_streams(
        cls, parsed_data: List[Dict[str, Any]], batch_id: int, db: AsyncSession
    ) -> Dict[str, int]:
        # Preload unique teacher names to avoid N+1 queries
        teacher_names = {
            s_data["teacher"] for s_data in parsed_data if s_data["teacher"]
        }

        existing_teachers = {}
        if teacher_names:
            stmt = select(Teacher).where(Teacher.name.in_(list(teacher_names)))
            res = await db.execute(stmt)
            for t in res.scalars().all():
                existing_teachers[t.name] = t.id

        # Insert missing teachers in bulk
        new_teachers = []
        for name in teacher_names:
            if name not in existing_teachers:
                new_teacher = Teacher(name=name)
                new_teachers.append(new_teacher)

        if new_teachers:
            db.add_all(new_teachers)
            await db.flush()
            for t in new_teachers:
                existing_teachers[t.name] = t.id

        group_sizes = {}
        for stream_data in parsed_data:
            for group in stream_data["groups"]:
                group_sizes[group["name"]] = max(
                    group_sizes.get(group["name"], 0), group["size"]
                )
        existing_groups = {}
        if group_sizes:
            result = await db.execute(
                select(StudentGroup).where(StudentGroup.name.in_(group_sizes))
            )
            existing_groups = {group.name: group for group in result.scalars()}

        for name, size in group_sizes.items():
            student_group = existing_groups.get(name)
            if student_group is None:
                student_group = StudentGroup(name=name, student_count=size)
                db.add(student_group)
                existing_groups[name] = student_group
            else:
                student_group.student_count = max(student_group.student_count, size)
        await db.flush()

        # Prepare and insert streams in bulk
        new_streams = []
        for s_data in parsed_data:
            teacher_clean = s_data["teacher"]
            teacher_id = existing_teachers.get(teacher_clean) if teacher_clean else None

            stream = Stream(
                import_batch_id=batch_id,
                teacher_id=teacher_id,
                event_name=s_data["event"],
                stream_type=s_data["type"],
                lessons_count=s_data.get("lessons_count", 1),
            )
            new_streams.append(stream)

        if new_streams:
            db.add_all(new_streams)
            await db.flush()

        # Prepare and insert groups in bulk
        new_groups = []
        for stream, s_data in zip(new_streams, parsed_data):
            for group in s_data["groups"]:
                new_group = StreamGroup(
                    stream_id=stream.id,
                    student_group_id=existing_groups[group["name"]].id,
                    group_name=group["name"],
                    group_size=group["size"],
                )
                new_groups.append(new_group)

        if new_groups:
            db.add_all(new_groups)
            await db.flush()

        return {
            "streams_added": len(new_streams),
            "groups_added": len(new_groups),
        }

    @classmethod
    async def import_teacher_availability(
        cls, df: pd.DataFrame, db: AsyncSession
    ) -> int:
        required_columns = {"ФИО преподавателя", "Режим"}
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Missing required columns: {missing}")

        rows_to_process: dict[str, dict[str, Any]] = {}

        for _, row in df.iterrows():
            name = str(row["ФИО преподавателя"]).strip()
            if not name or name == "nan":
                continue

            mode = str(row["Режим"]).strip()
            recurring = str(row.get("Регулярные окна (День_Пара)", "")).strip()
            specific = str(row.get("Конкретные даты (ГГГГ-ММ-ДД_Пара)", "")).strip()

            rec_list = (
                [i.strip() for i in recurring.split(",") if i.strip()]
                if recurring and recurring != "nan"
                else []
            )
            spec_list = (
                [i.strip() for i in specific.split(",") if i.strip()]
                if specific and specific != "nan"
                else []
            )
            for value in rec_list:
                try:
                    js_day, lesson = value.split("-", 1)
                    if int(js_day) not in range(7) or int(lesson) not in range(1, 8):
                        raise ValueError
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid recurring restriction for {name}: {value}"
                    ) from exc
            for value in spec_list:
                try:
                    date_string, lesson = value.rsplit("-", 1)
                    pd.Timestamp(date_string)
                    if int(lesson) not in range(1, 8):
                        raise ValueError
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Invalid specific restriction for {name}: {value}"
                    ) from exc

            restr = {
                "mode": mode if mode in ["blacklist", "whitelist"] else "blacklist",
                "recurring": rec_list,
                "specific": spec_list,
                "intervals": [],
            }

            rows_to_process[name] = restr

        if not rows_to_process:
            return 0

        # Preload teachers to update
        stmt = select(Teacher).where(Teacher.name.in_(rows_to_process))
        res = await db.execute(stmt)
        teachers_map = {t.name: t for t in res.scalars().all()}

        teacher_ids = [teacher.id for teacher in teachers_map.values()]
        if teacher_ids:
            await db.execute(
                delete(AvailabilityRule).where(
                    AvailabilityRule.teacher_id.in_(teacher_ids)
                )
            )

        structured_rules: list[AvailabilityRule] = []
        for name, teacher in teachers_map.items():
            restrictions = rows_to_process[name]
            teacher.restrictions_json = json.dumps(restrictions)
            rule_kind = (
                "available"
                if restrictions["mode"] == "whitelist"
                else "unavailable"
            )
            for value in restrictions["recurring"]:
                js_day, lesson = value.split("-", 1)
                structured_rules.append(
                    AvailabilityRule(
                        teacher_id=teacher.id,
                        rule_kind=rule_kind,
                        recurrence="weekly",
                        weekday=(int(js_day) - 1) % 7,
                        lesson_start=int(lesson),
                        lesson_end=int(lesson),
                        is_hard=True,
                    )
                )
            for value in restrictions["specific"]:
                date_string, lesson = value.rsplit("-", 1)
                structured_rules.append(
                    AvailabilityRule(
                        teacher_id=teacher.id,
                        rule_kind=rule_kind,
                        recurrence="specific",
                        specific_date=pd.Timestamp(date_string).date(),
                        lesson_start=int(lesson),
                        lesson_end=int(lesson),
                        is_hard=True,
                    )
                )
        db.add_all(structured_rules)
        return len(teachers_map)
