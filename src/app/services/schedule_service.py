import json
import logging
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.all_models import (
    ScheduleEntry,
    Teacher,
    Stream,
    StreamGroup,
)

logger = logging.getLogger(__name__)


class ScheduleService:
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
            else:
                e.warning = None

        for (_d, _l), slot_entries in by_slot.items():
            for e1 in slot_entries:
                slot_warnings: List[str] = []

                # 1. Overlap checks
                for e2 in slot_entries:
                    if e1.id == e2.id:
                        continue

                    # Same teacher = conflict (unless same event+group = stream lecture)
                    if (
                        e1.teacher_id
                        and e1.teacher_id == e2.teacher_id
                        and not (
                            e1.event_name == e2.event_name
                            and e1.stream_type == e2.stream_type
                            and e1.stream_type in ("Лекция", "lecture")
                        )
                    ):
                        slot_warnings.append(
                            f"Преподаватель занят: {e2.event_name} ({e2.group_name})"
                        )

                    # Same group = real conflict
                    if e1.group_name == e2.group_name:
                        slot_warnings.append(
                            f"У группы {e1.group_name} уже есть пара ({e2.event_name})"
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
                                        if int(d_s) == js_weekday and int(l_s) == lesson:
                                            is_in_recurring = True
                                            break
                                    except Exception:
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
                                    except Exception:
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
    async def get_task_entries_json(cls, task_id: int, db: AsyncSession) -> List[Dict[str, Any]]:
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
            }
            for e in entries
        ]

    @classmethod
    async def import_streams(cls, parsed_data: List[Dict[str, Any]], batch_id: int, db: AsyncSession) -> Dict[str, int]:
        # Preload unique teacher names to avoid N+1 queries
        teacher_names = {s_data["teacher"] for s_data in parsed_data if s_data["teacher"]}
        
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
    async def import_teacher_availability(cls, df: pd.DataFrame, db: AsyncSession) -> int:
        teacher_names = []
        rows_to_process = []

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

            restr = {
                "mode": mode if mode in ["blacklist", "whitelist"] else "blacklist",
                "recurring": rec_list,
                "specific": spec_list,
            }

            teacher_names.append(name)
            rows_to_process.append((name, restr))

        if not teacher_names:
            return 0

        # Preload teachers to update
        stmt = select(Teacher).where(Teacher.name.in_(teacher_names))
        res = await db.execute(stmt)
        teachers_map = {t.name: t for t in res.scalars().all()}

        updated_count = 0
        for name, restr in rows_to_process:
            teacher = teachers_map.get(name)
            if teacher:
                teacher.restrictions_json = json.dumps(restr)
                updated_count += 1

        return updated_count
