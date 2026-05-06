import json
import logging
from datetime import datetime
from typing import List

import anyio
from core.config import sessionmaker
from core.constants import (
    DEFAULT_START_DATE, DEFAULT_END_DATE, STUDY_DAYS, LESSONS,
    ROOMS as DEFAULT_ROOMS, MAX_TIME_SECONDS
)
from database.all_models import Stream, ScheduleEntry, StreamGroup, GenerationTask
from services.scheduler_engine import solve_schedule
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

class GenerationService:
    @staticmethod
    async def get_subjects_summary(selected_groups: List[str], enabled_types: List[str]):
        """Returns subjects grouped by direction (prefix before /)"""
        async with sessionmaker() as session:
            stmt = (
                select(Stream)
                .join(Stream.groups)
                .filter(StreamGroup.group_name.in_(selected_groups))
                .filter(Stream.is_ignored == False)
                .filter(Stream.stream_type.in_(enabled_types))
                .options(selectinload(Stream.groups))
            )
            result = await session.execute(stmt)
            streams = result.unique().scalars().all()
            
            summary = {} # { "Direction": set(["Subject1", "Subject2"]) }
            for s in streams:
                # Extract direction: "ИОП-ИТ-25/1" -> "ИОП-ИТ-25"
                for g in s.groups:
                    if g.group_name in selected_groups:
                        direction = g.group_name.split("/")[0] if "/" in g.group_name else "Общее"
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
        end_date_str: str | None = None
    ):
        logger.info(f"Starting generation for task {task_id}, groups: {selected_groups}")
        
        # 1. Convert holidays to date objects
        holidays = []
        for h in holidays_str:
            try:
                holidays.append(datetime.strptime(h, "%Y-%m-%d").date())
            except:
                pass
        
        async with sessionmaker() as session:
            try:
                # 0. Fetch task settings for priorities
                task = await session.get(GenerationTask, task_id)
                settings = json.loads(task.settings_json) if task and task.settings_json else {}
                priorities = settings.get("priorities", {})

                # 2. Fetch all relevant streams from DB
                stmt = (
                    select(Stream)
                    .join(Stream.groups)
                    .filter(StreamGroup.group_name.in_(selected_groups))
                    .filter(Stream.is_ignored == False)
                    .filter(Stream.stream_type.in_(enabled_types))
                    .options(selectinload(Stream.groups), selectinload(Stream.teacher))
                )
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
                
                from collections import defaultdict
                grouped = defaultdict(list)
                for s in streams:
                    grouped[s.event_name].append(s)

                for event_name, event_streams in grouped.items():
                    lecs = [s for s in event_streams if s.stream_type == 'Лекция']
                    sems = [s for s in event_streams if s.stream_type == 'Семинар']
                    labs = [s for s in event_streams if s.stream_type == 'Лабораторная']
                    
                    main_t = "Неизвестно"
                    all_teachers = [s.teacher.name for s in event_streams if s.teacher]
                    if all_teachers: main_t = all_teachers[0]

                    lec_groups = []
                    for s in lecs: lec_groups.extend(
                        [g.group_name for g in s.groups if g.group_name in selected_groups])
                    
                    sem_groups = []
                    for s in sems: sem_groups.extend(
                        [g.group_name for g in s.groups if g.group_name in selected_groups])

                    lab_groups = []
                    for s in labs: lab_groups.extend(
                        [g.group_name for g in s.groups if g.group_name in selected_groups])

                    subjects_engine[event_name] = {
                        "display_name": event_name,
                        "teacher": main_t,
                        "lectures": lecs[0].lessons_count if lecs else 0,
                        "seminars": sems[0].lessons_count if sems else 0,
                        "labs": labs[0].lessons_count if labs else 0
                    }
                    streams_map_engine[event_name] = sorted(list(set(lec_groups + sem_groups + lab_groups)))
                    
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
                                                        d_str, l_str = str(item).split(sep)
                                                        d = int(d_str) - 1
                                                        l = int(l_str)
                                                        selected_slots.append((d, l))
                                                        break
                                                    except: continue
                                    
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
                                                            dt = datetime.strptime(d_str, "%Y-%m-%d").date()
                                                            l = int(l_str)
                                                            specific_slots.append((dt, l))
                                                            break
                                                    except: continue

                                    if mode == "whitelist":
                                        for d_idx in [0, 1, 2, 3, 4, 5]:
                                            for l in [1, 2, 3, 4, 5, 6, 7]:
                                                if (d_idx, l) not in selected_slots:
                                                    unavailable_list.append((d_idx, l))
                                    else:
                                        unavailable_list.extend(selected_slots)
                                        unavailable_list.extend(specific_slots)
                                
                                unavailable_times["teacher"][teacher_name] = unavailable_list
                            except Exception as e:
                                logger.error(f"Error parsing restrictions for {teacher_name}: {e}")

                START_DATE = DEFAULT_START_DATE
                if start_date_str:
                    try:
                        START_DATE = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    except: pass
                
                END_DATE = DEFAULT_END_DATE
                if end_date_str:
                    try:
                        END_DATE = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    except: pass
                    
                final_schedule, slots, warnings = await anyio.to_thread.run_sync(
                    solve_schedule, START_DATE, END_DATE, STUDY_DAYS, LESSONS, holidays,
                    selected_groups, group_sizes_engine, subjects_engine, streams_map_engine,
                    DEFAULT_ROOMS, unavailable_times, None, MAX_TIME_SECONDS, priorities
                )

                if final_schedule:
                    new_entries = []
                    for entry in final_schedule:
                        s_id = entry["subject"]
                        subj_info = subjects_engine.get(s_id, {})
                        display_name = subj_info.get("display_name", "Unknown").split(" (")[0]
                        
                        new_entries.append(ScheduleEntry(
                            task_id=task_id,
                            group_name=entry["group"],
                            event_name=display_name,
                            stream_type="Лекция" if entry["type"] == "lec" else (
                                "Лабораторная" if entry["type"] == "lab" else "Семинар"),
                            teacher_name=entry["teacher"],
                            room_name=entry["room"],
                            date=datetime.combine(entry["slot"][0], datetime.min.time()),
                            lesson_number=entry["slot"][1],
                            warning=entry.get("warning")
                        ))
                    
                    session.add_all(new_entries)
                    await session.execute(
                        update(GenerationTask)
                        .where(GenerationTask.id == task_id)
                        .values(status="success", result_count=len(new_entries))
                    )
                    await session.commit()
                    logger.info(f"Task {task_id} finished. Saved {len(new_entries)} entries.")
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
