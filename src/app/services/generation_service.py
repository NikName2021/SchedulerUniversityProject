import json
import logging
from typing import List, Dict
from datetime import datetime, date
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from core.config import sessionmaker
from database.all_models import Stream, Teacher, ScheduleEntry, StreamGroup, GenerationTask
from services.scheduler_engine import solve_schedule

logger = logging.getLogger(__name__)

class GenerationService:
    @staticmethod
    async def run_generation(
        task_id: int,
        selected_groups: List[str],
        holidays_str: List[str],
        enabled_types: List[str]
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
                
                for s in streams:
                    engine_key = f"{s.event_name} ({s.stream_type})"
                    teacher_name = s.teacher.name if s.teacher else "Неизвестно"
                    
                    is_lec = s.stream_type == 'Лекция'
                    subjects_engine[engine_key] = {
                        "teacher": teacher_name,
                        "lectures": 1 if is_lec else 0,
                        "seminars": 0 if is_lec else 1,
                        "type_sem": "sem" if s.stream_type == 'Семинар' else "lab" if s.stream_type == 'Лабораторная' else "sem"
                    }
                    
                    g_names = [g.group_name for g in s.groups if g.group_name in selected_groups]
                    streams_map_engine[engine_key] = g_names
                    
                    for g in s.groups:
                        group_sizes_engine[g.group_name] = g.group_size
                    
                    if s.teacher and s.teacher.restrictions_json:
                        try:
                            restrs = json.loads(s.teacher.restrictions_json)
                            unavailable_list = []
                            if isinstance(restrs, dict):
                                recurring = restrs.get("recurring", {})
                                if isinstance(recurring, dict):
                                    for day_idx_str, lessons in recurring.items():
                                        try:
                                            day_idx = int(day_idx_str)
                                            for l in lessons:
                                                unavailable_list.append((day_idx, l))
                                        except: continue
                            elif isinstance(restrs, list):
                                for item in restrs:
                                    if ":" in str(item):
                                        try:
                                            d, l = map(int, str(item).split(":"))
                                            unavailable_list.append((d, l))
                                        except: continue
                            unavailable_times["teacher"][teacher_name] = unavailable_list
                        except Exception as e:
                            logger.error(f"Error parsing restrictions for {teacher_name}: {e}")

                START_DATE = date(2025, 9, 1)
                END_DATE = date(2025, 9, 7)
                STUDY_DAYS = [0, 1, 2, 3, 4, 5]
                LESSONS = [1, 2, 3, 4, 5, 6]
                
                ROOMS = {
                    "101": {"capacity": 30, "type": "sem"},
                    "102": {"capacity": 20, "type": "sem"},
                    "103": {"capacity": 80, "type": "lec"},
                    "104": {"capacity": 60, "type": "lec"},
                    "105": {"capacity": 15, "type": "lab"},
                    "106": {"capacity": 30, "type": "sem"},
                }

                import anyio
                final_schedule, slots, warnings = await anyio.to_thread.run_sync(
                    solve_schedule, START_DATE, END_DATE, STUDY_DAYS, LESSONS, holidays,
                    selected_groups, group_sizes_engine, subjects_engine, streams_map_engine,
                    ROOMS, unavailable_times, None, 60
                )

                if final_schedule:
                    new_entries = []
                    for entry in final_schedule:
                        event_name = entry["subject"].split(" (")[0]
                        new_entries.append(ScheduleEntry(
                            task_id=task_id,
                            group_name=entry["group"],
                            event_name=event_name,
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
