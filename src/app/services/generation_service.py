import json
import logging
from typing import List, Dict
from datetime import datetime, date
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from core.config import sessionmaker
from database.all_models import Stream, Teacher, ScheduleEntry, StreamGroup, GenerationTask
from services.scheduler_engine import solve_schedule
from core.constants import (
    DEFAULT_START_DATE, DEFAULT_END_DATE, STUDY_DAYS, LESSONS, 
    ROOMS as DEFAULT_ROOMS, MAX_TIME_SECONDS
)

logger = logging.getLogger(__name__)

class GenerationService:
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
                    lec_s = next((s for s in event_streams if s.stream_type == 'Лекция'), None)
                    sem_s = [s for s in event_streams if s.stream_type != 'Лекция']
                    
                    main_t = "Неизвестно"
                    if lec_s and lec_s.teacher: main_t = lec_s.teacher.name
                    elif sem_s and sem_s[0].teacher: main_t = sem_s[0].teacher.name

                    lec_groups = [g.group_name for g in lec_s.groups if g.group_name in selected_groups] if lec_s else []
                    sem_groups = []
                    for ss in sem_s:
                        sem_groups.extend([g.group_name for g in ss.groups if g.group_name in selected_groups])

                    subjects_engine[event_name] = {
                        "display_name": event_name,
                        "teacher": main_t,
                        "lectures": lec_s.lessons_count if lec_s else 0,
                        "seminars": sem_s[0].lessons_count if sem_s else 0,
                        "type_sem": "lab" if any(ss.stream_type == 'Лабораторная' for ss in sem_s) else "sem"
                    }
                    streams_map_engine[event_name] = sorted(list(set(lec_groups + sem_groups)))
                    
                    for s in event_streams:
                        for g in s.groups:
                            group_sizes_engine[g.group_name] = g.group_size
                    
                    if s.teacher and s.teacher.restrictions_json:
                        try:
                            restrs = json.loads(s.teacher.restrictions_json)
                            unavailable_list = []
                            
                            # Handle both old dict format and new list format
                            if isinstance(restrs, dict):
                                # Mode handling
                                mode = restrs.get("mode", "blacklist")
                                
                                # Recurring
                                recurring_keys = restrs.get("recurring", [])
                                selected_slots = []
                                if isinstance(recurring_keys, list):
                                    for item in recurring_keys:
                                        # Handle "1-1", "1_1", "1:1"
                                        for sep in ["-", "_", ":"]:
                                            if sep in str(item):
                                                try:
                                                    d_str, l_str = str(item).split(sep)
                                                    d = int(d_str) - 1 # JS 1=Mon -> Python 0=Mon
                                                    l = int(l_str)
                                                    selected_slots.append((d, l))
                                                    break
                                                except: continue
                                                
                                # Specific
                                specific_keys = restrs.get("specific", [])
                                specific_slots = []
                                if isinstance(specific_keys, list):
                                    for item in specific_keys:
                                        # Handle "2025-09-01-1", "2025-09-01_1"
                                        for sep in ["-", "_", ":"]:
                                            if sep in str(item):
                                                try:
                                                    parts = str(item).split(sep)
                                                    if len(parts) >= 4: # YYYY-MM-DD-Slot
                                                        d_str = "-".join(parts[:3])
                                                        l_str = parts[3]
                                                        dt = datetime.strptime(d_str, "%Y-%m-%d").date()
                                                        l = int(l_str)
                                                        specific_slots.append((dt, l))
                                                        break
                                                except: continue

                                if mode == "whitelist":
                                    # Block all slots EXCEPT selected ones
                                    # Note: Whitelist for specific dates is tricky, usually we only whitelist recurring
                                    for d_idx in [0, 1, 2, 3, 4, 5]: # Mon-Sat
                                        for l in [1, 2, 3, 4, 5, 6, 7]: # 7 lessons
                                            if (d_idx, l) not in selected_slots:
                                                unavailable_list.append((d_idx, l))
                                    # For specific slots in whitelist mode, they are handled as exceptions
                                    # (This is a design choice, usually whitelist = recurring availability)
                                else:
                                    # Blacklist mode: Block selected slots
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
                    
                import anyio
                final_schedule, slots, warnings = await anyio.to_thread.run_sync(
                    solve_schedule, START_DATE, END_DATE, STUDY_DAYS, LESSONS, holidays,
                    selected_groups, group_sizes_engine, subjects_engine, streams_map_engine,
                    DEFAULT_ROOMS, unavailable_times, None, MAX_TIME_SECONDS
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
                            stream_type="Лекция" if entry["type"] == "lec" else "Семинар",
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
