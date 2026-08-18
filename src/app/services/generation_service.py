import collections
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

import anyio
from core.config import sessionmaker
from core.constants import (
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    LESSONS,
    MAX_TIME_SECONDS,
    ROOM_FUND_ENABLED,
    STUDY_DAYS,
)
from core.constants import ROOMS as DEFAULT_ROOMS
from database.all_models import (
    GenerationTask,
    ScheduleEntry,
    Stream,
    StreamGroup,
    WeeklyLessonDemand,
)
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from services.scheduler_engine import solve_schedule

logger = logging.getLogger(__name__)


class GenerationService:
    @staticmethod
    async def get_subjects_summary(
        selected_groups: List[str], enabled_types: List[str]
    ) -> Dict[str, List[str]]:
        """Returns subjects grouped by direction (prefix before /)"""
        async with sessionmaker() as session:
            stmt = (
                select(Stream)
                .join(Stream.groups)
                .filter(StreamGroup.group_name.in_(selected_groups))
                .filter(Stream.is_ignored.is_(False))
                .filter(Stream.stream_type.in_(enabled_types))
                .options(selectinload(Stream.groups))
            )
            result = await session.execute(stmt)
            streams = result.unique().scalars().all()

            summary = {}  # { "Direction": set(["Subject1", "Subject2"]) }
            for s in streams:
                # Extract direction: "ИОП-ИТ-25/1" -> "ИОП-ИТ-25"
                for g in s.groups:
                    if g.group_name in selected_groups:
                        direction = (
                            g.group_name.split("/")[0]
                            if "/" in g.group_name
                            else "Общее"
                        )
                        if direction not in summary:
                            summary[direction] = set()
                        summary[direction].add(s.event_name)

            return {d: sorted(list(subs)) for d, subs in summary.items()}

    @staticmethod
    async def run_generation(
        task_id: int,
        selected_groups: List[str],
        holidays_str: List[str],
        enabled_types: List[str],
        start_date_str: str | None = None,
        end_date_str: str | None = None,
        planning_week_id: int | None = None,
    ) -> Optional[bool]:
        logger.info(
            f"Starting generation for task {task_id}, groups: {selected_groups}"
        )

        # 1. Convert holidays to date objects
        holidays = []
        for h in holidays_str:
            try:
                holidays.append(datetime.strptime(h, "%Y-%m-%d").date())
            except (TypeError, ValueError):
                logger.warning("Ignoring invalid holiday value: %r", h)

        async with sessionmaker() as session:
            try:
                # 0. Fetch task settings for priorities
                task = await session.get(GenerationTask, task_id)
                if task and task.status == "success":
                    logger.info("Task %s is already complete; skipping retry", task_id)
                    return True
                if task:
                    task.status = "running"
                    task.error_message = None
                    await session.commit()
                settings = (
                    json.loads(task.settings_json)
                    if task and task.settings_json
                    else {}
                )
                priorities = settings.get("priorities", {})

                weekly_counts: dict[int, int] = {}
                if planning_week_id is not None:
                    demand_result = await session.execute(
                        select(WeeklyLessonDemand).where(
                            WeeklyLessonDemand.week_id == planning_week_id
                        )
                    )
                    weekly_demands = list(demand_result.scalars().all())
                    if not weekly_demands:
                        task.status = "failed"
                        task.error_message = (
                            "Weekly lesson demand is not configured for this week"
                        )
                        await session.commit()
                        return False
                    weekly_counts = {
                        demand.stream_id: demand.lessons_count
                        for demand in weekly_demands
                    }

                # 2. Fetch all relevant streams from DB
                stmt = (
                    select(Stream)
                    .join(Stream.groups)
                    .filter(StreamGroup.group_name.in_(selected_groups))
                    .filter(Stream.is_ignored.is_(False))
                    .filter(Stream.stream_type.in_(enabled_types))
                    .options(selectinload(Stream.groups), selectinload(Stream.teacher))
                )
                if planning_week_id is not None:
                    active_stream_ids = [
                        stream_id
                        for stream_id, count in weekly_counts.items()
                        if count > 0
                    ]
                    stmt = stmt.filter(Stream.id.in_(active_stream_ids))
                result = await session.execute(stmt)
                streams = result.unique().scalars().all()

                if not streams:
                    logger.warning(f"No streams found for task {task_id}")
                    await session.execute(
                        update(GenerationTask)
                        .where(GenerationTask.id == task_id)
                        .values(status="failed", error_message="No streams found")
                    )
                    await session.commit()
                    return False

                subjects_engine = {}
                streams_map_engine = {}
                group_sizes_engine = {}
                unavailable_times = {"teacher": {}, "group": {}, "room": {}}

                grouped = collections.defaultdict(list)
                for s in streams:
                    grouped[s.event_name].append(s)

                for event_name, event_streams in grouped.items():
                    lecs = [s for s in event_streams if s.stream_type == "Лекция"]
                    sems = [s for s in event_streams if s.stream_type == "Семинар"]
                    labs = [s for s in event_streams if s.stream_type == "Лабораторная"]

                    main_t = "Неизвестно"
                    main_t_id = None
                    all_teachers_info = [
                        (s.teacher.name, s.teacher.id)
                        for s in event_streams
                        if s.teacher
                    ]
                    if all_teachers_info:
                        main_t, main_t_id = all_teachers_info[0]

                    lec_groups = []
                    for s in lecs:
                        lec_groups.extend(
                            [
                                g.group_name
                                for g in s.groups
                                if g.group_name in selected_groups
                            ]
                        )

                    sem_groups = []
                    for s in sems:
                        sem_groups.extend(
                            [
                                g.group_name
                                for g in s.groups
                                if g.group_name in selected_groups
                            ]
                        )

                    lab_groups = []
                    for s in labs:
                        lab_groups.extend(
                            [
                                g.group_name
                                for g in s.groups
                                if g.group_name in selected_groups
                            ]
                        )

                    subjects_engine[event_name] = {
                        "display_name": event_name,
                        "teacher": main_t,
                        "teacher_id": main_t_id,
                        "lectures": max(
                            (weekly_counts.get(s.id, s.lessons_count) for s in lecs),
                            default=0,
                        ),
                        "seminars": max(
                            (weekly_counts.get(s.id, s.lessons_count) for s in sems),
                            default=0,
                        ),
                        "labs": max(
                            (weekly_counts.get(s.id, s.lessons_count) for s in labs),
                            default=0,
                        ),
                        "stream_ids": {
                            "lec": lecs[0].id if lecs else None,
                            "sem": sems[0].id if sems else None,
                            "lab": labs[0].id if labs else None,
                        },
                    }
                    streams_map_engine[event_name] = sorted(
                        list(set(lec_groups + sem_groups + lab_groups))
                    )

                    for s in event_streams:
                        for g in s.groups:
                            group_sizes_engine[g.group_name] = g.group_size

                        if s.teacher and s.teacher.restrictions_json:
                            teacher_name = s.teacher.name
                            try:
                                restrs = json.loads(s.teacher.restrictions_json)
                                unavailable_list = []
                                if isinstance(restrs, dict):
                                    mode = restrs.get("mode", "blacklist")
                                    recurring_keys = restrs.get("recurring", [])
                                    selected_slots = []
                                    if isinstance(recurring_keys, list):
                                        for item in recurring_keys:
                                            for sep in ["-", "_", ":"]:
                                                if sep in str(item):
                                                    try:
                                                        d_str, l_str = str(item).split(
                                                            sep
                                                        )
                                                        # JS getDay(): 0=Sun, 1=Mon, ..., 6=Sat
                                                        # Engine weekday(): 0=Mon, ..., 6=Sun
                                                        # Convert: JS 1-6 → Python 0-5, 0 → 6
                                                        js_day = int(d_str)
                                                        py_day = (js_day - 1) % 7
                                                        lesson_num = int(l_str)
                                                        selected_slots.append(
                                                            (py_day, lesson_num)
                                                        )
                                                        break
                                                    except (TypeError, ValueError):
                                                        continue

                                    specific_keys = restrs.get("specific", [])
                                    specific_slots = []
                                    if isinstance(specific_keys, list):
                                        for item in specific_keys:
                                            for sep in ["-", "_", ":"]:
                                                if sep in str(item):
                                                    try:
                                                        parts = str(item).split(sep)
                                                        if len(parts) >= 4:
                                                            d_str = "-".join(parts[:3])
                                                            l_str = parts[3]
                                                            dt = datetime.strptime(
                                                                d_str, "%Y-%m-%d"
                                                            ).date()
                                                            lesson_num = int(l_str)
                                                            specific_slots.append(
                                                                (dt, lesson_num)
                                                            )
                                                            break
                                                    except (TypeError, ValueError):
                                                        continue

                                    if mode == "whitelist":
                                        for d_idx in [0, 1, 2, 3, 4, 5]:
                                            for l_idx in [1, 2, 3, 4, 5, 6, 7]:
                                                if (d_idx, l_idx) not in selected_slots:
                                                    unavailable_list.append(
                                                        (d_idx, l_idx)
                                                    )
                                    else:
                                        unavailable_list.extend(selected_slots)
                                        unavailable_list.extend(specific_slots)

                                unavailable_times["teacher"][teacher_name] = (
                                    unavailable_list
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error parsing restrictions for "
                                    f"{teacher_name}: {e}"
                                )

                START_DATE = DEFAULT_START_DATE
                if start_date_str:
                    try:
                        START_DATE = datetime.strptime(
                            start_date_str, "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        pass

                END_DATE = DEFAULT_END_DATE
                if end_date_str:
                    try:
                        END_DATE = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    except ValueError:
                        pass

                final_schedule, slots, warnings = await anyio.to_thread.run_sync(
                    solve_schedule,
                    START_DATE,
                    END_DATE,
                    STUDY_DAYS,
                    LESSONS,
                    holidays,
                    selected_groups,
                    group_sizes_engine,
                    subjects_engine,
                    streams_map_engine,
                    DEFAULT_ROOMS if ROOM_FUND_ENABLED else {},
                    unavailable_times,
                    None,
                    MAX_TIME_SECONDS,
                    priorities,
                )

                if final_schedule:
                    new_entries = []
                    for entry in final_schedule:
                        s_id = entry["subject"]
                        subj_info = subjects_engine.get(s_id, {})
                        display_name = subj_info.get("display_name", "Unknown").split(
                            " ("
                        )[0]

                        new_entries.append(
                            ScheduleEntry(
                                task_id=task_id,
                                planning_week_id=planning_week_id,
                                source_stream_id=subj_info.get("stream_ids", {}).get(
                                    entry["type"]
                                ),
                                group_name=entry["group"],
                                event_name=display_name,
                                stream_type="Лекция"
                                if entry["type"] == "lec"
                                else (
                                    "Лабораторная"
                                    if entry["type"] == "lab"
                                    else "Семинар"
                                ),
                                teacher_id=entry.get("teacher_id"),
                                room_id=entry.get("room"),
                                date=datetime.combine(
                                    entry["slot"][0], datetime.min.time()
                                ),
                                lesson_number=entry["slot"][1],
                                warning=entry.get("warning"),
                            )
                        )

                    session.add_all(new_entries)

                    # --- Save Unassigned Entries ---
                    unassigned_entries = []
                    for warn in [
                        w for w in warnings if isinstance(w, dict) and "count" in w
                    ]:
                        s_id = warn["subject"]
                        subj_info = subjects_engine.get(s_id, {})
                        display_name = subj_info.get("display_name", s_id).split(" (")[
                            0
                        ]

                        count = warn.get("count", 1)
                        for _ in range(count):
                            unassigned_entries.append(
                                ScheduleEntry(
                                    task_id=task_id,
                                    planning_week_id=planning_week_id,
                                    source_stream_id=subj_info.get(
                                        "stream_ids", {}
                                    ).get(warn["type"]),
                                    group_name=warn["group"],
                                    event_name=display_name,
                                    stream_type="Лекция"
                                    if warn["type"] == "lec"
                                    else (
                                        "Лабораторная"
                                        if warn["type"] == "lab"
                                        else "Семинар"
                                    ),
                                    teacher_id=subj_info.get("teacher_id"),
                                    date=None,
                                    lesson_number=None,
                                    warning=warn["msg"],
                                )
                            )
                    if unassigned_entries:
                        session.add_all(unassigned_entries)

                    total_saved = len(new_entries) + len(unassigned_entries)
                    await session.execute(
                        update(GenerationTask)
                        .where(GenerationTask.id == task_id)
                        .values(status="success", result_count=total_saved)
                    )
                    await session.commit()
                    logger.info(
                        f"Task {task_id} finished. Saved {len(new_entries)} entries."
                    )
                    return True
                else:
                    await session.execute(
                        update(GenerationTask)
                        .where(GenerationTask.id == task_id)
                        .values(status="failed", error_message=str(warnings))
                    )
                    await session.commit()
                    logger.error(f"Task {task_id} failed: {warnings}")
                    return False
            except Exception as e:
                logger.exception(f"Exception during task {task_id}: {e}")
                await session.execute(
                    update(GenerationTask)
                    .where(GenerationTask.id == task_id)
                    .values(status="failed", error_message=str(e))
                )
                await session.commit()
                return False
