import json
import logging
import os
import uuid
from datetime import datetime

from core.config import async_get_db
from database.all_models import (
    FileType,
    GenerationTask,
    ImportBatch,
    ScheduleEntry,
    Stream,
    StreamGroup,
    Teacher,
)
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.export_service import generate_excel_report
from services.generation_service import GenerationService
from services.parser_service import parse_streams_content
from sqlalchemy import distinct, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "../../uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class StreamUpdateModel(BaseModel):
    stream_type: str | None = None
    is_ignored: bool | None = None


class TeacherRestrictionsDetails(BaseModel):
    mode: str
    specific: list[str]
    recurring: list[str]


class TeacherRestrictionsModel(BaseModel):
    restrictions: TeacherRestrictionsDetails


class GenerationTaskModel(BaseModel):
    groups: list[str]
    holidays: list[str]
    start_date: str | None = None
    end_date: str | None = None
    settings: dict | None = None


class ScheduleUpdateModel(BaseModel):
    lesson_number: int | None = None
    date: str | None = None
    teacher_id: int | None = None
    room_id: str | None = None  # room_id is string in model


@router.post("/import/streams")
async def import_streams(
    file: UploadFile = File(...), db: AsyncSession = Depends(async_get_db)
):
    if not file.filename.endswith((".xls", ".xlsx", ".csv")):
        raise HTTPException(status_code=400, detail="Invalid file type")

    content = await file.read()

    try:
        parsed_data = parse_streams_content(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing file: {str(e)}")

    if not parsed_data:
        raise HTTPException(status_code=400, detail="No streams found in the document")

    # Save file to disk
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # Create ImportBatch
    batch = ImportBatch(
        filename=file.filename,
        file_path=file_path,
        file_type=FileType.STREAMS,
        status="completed",
    )
    db.add(batch)
    await db.flush()

    added_streams_count = 0
    added_groups_count = 0

    for s_data in parsed_data:
        teacher_clean = s_data["teacher"]
        teacher_id = None

        if teacher_clean:
            stmt = select(Teacher).where(Teacher.name == teacher_clean)
            result = await db.execute(stmt)
            existing_teacher = result.scalar_one_or_none()

            if not existing_teacher:
                new_teacher = Teacher(name=teacher_clean)
                db.add(new_teacher)
                await db.flush()
                teacher_id = new_teacher.id
            else:
                teacher_id = existing_teacher.id

        new_stream = Stream(
            import_batch_id=batch.id,
            teacher_id=teacher_id,
            event_name=s_data["event"],
            stream_type=s_data["type"],
            lessons_count=s_data.get("lessons_count", 1),
        )
        db.add(new_stream)
        await db.flush()
        added_streams_count += 1

        for group in s_data["groups"]:
            new_group = StreamGroup(
                stream_id=new_stream.id,
                group_name=group["name"],
                group_size=group["size"],
            )
            db.add(new_group)
            added_groups_count += 1

    await db.commit()

    return {
        "detail": "Success",
        "batch_id": batch.id,
        "streams_added": added_streams_count,
        "groups_added": added_groups_count,
    }


@router.get("/import/history")
async def get_import_history(db: AsyncSession = Depends(async_get_db)):
    stmt = select(ImportBatch).order_by(ImportBatch.created_date.desc())
    result = await db.execute(stmt)
    batches = result.scalars().all()

    return [
        {
            "id": b.id,
            "filename": b.filename,
            "file_type": b.file_type.value,
            "created_date": b.created_date,
            "status": getattr(b, "status", "completed"),
        }
        for b in batches
    ]


@router.delete("/import/history/{batch_id}")
async def delete_import_batch(batch_id: int, db: AsyncSession = Depends(async_get_db)):
    stmt = select(ImportBatch).where(ImportBatch.id == batch_id)
    result = await db.execute(stmt)
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if batch.file_path and os.path.exists(batch.file_path):
        try:
            os.remove(batch.file_path)
        except OSError as e:
            logger.error(f"Error deleting file {batch.file_path}: {e}")

    await db.delete(batch)
    await db.commit()
    return {"detail": "Import batch and associated data deleted"}


@router.get("/groups")
async def get_groups(db: AsyncSession = Depends(async_get_db)):
    stmt = select(distinct(StreamGroup.group_name)).order_by(StreamGroup.group_name)
    result = await db.execute(stmt)
    groups = result.scalars().all()
    return {"groups": groups}


@router.get("/subjects-summary")
async def get_subjects_summary(
    groups: str = Query(...),  # Comma separated
    types: str = Query(...),  # Comma separated
):
    selected_groups = groups.split(",")
    enabled_types = types.split(",")
    try:
        from services.generation_service import GenerationService

        summary = await GenerationService.get_subjects_summary(
            selected_groups, enabled_types
        )
        return summary
    except Exception as e:
        logger.error(f"Error getting subjects summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/streams")
async def get_streams_by_group(
    group_name: str = Query(..., description="Group name filter"),
    db: AsyncSession = Depends(async_get_db),
):
    stmt = (
        select(Stream)
        .join(StreamGroup, StreamGroup.stream_id == Stream.id)
        .where(StreamGroup.group_name == group_name)
        .options(selectinload(Stream.teacher), selectinload(Stream.groups))
    )
    result = await db.execute(stmt)
    streams = result.scalars().all()

    response = []
    for s in streams:
        response.append(
            {
                "id": s.id,
                "event_name": s.event_name,
                "stream_type": s.stream_type,
                "is_ignored": s.is_ignored,
                "teacher": s.teacher.name if s.teacher else None,
                "groups": [
                    {"name": g.group_name, "size": g.group_size} for g in s.groups
                ],
            }
        )

    return response


@router.patch("/streams/{stream_id}")
async def update_stream(
    stream_id: int, payload: StreamUpdateModel, db: AsyncSession = Depends(async_get_db)
):
    stmt = select(Stream).where(Stream.id == stream_id)
    result = await db.execute(stmt)
    stream = result.scalar_one_or_none()

    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    if payload.stream_type is not None:
        stream.stream_type = payload.stream_type
    if payload.is_ignored is not None:
        stream.is_ignored = payload.is_ignored

    await db.commit()
    return {"detail": "Stream updated successfully"}


@router.get("/teachers")
async def get_teachers(db: AsyncSession = Depends(async_get_db)):
    stmt = select(Teacher).order_by(Teacher.name)
    result = await db.execute(stmt)
    teachers = result.scalars().all()

    response = []
    for t in teachers:
        blocked = []
        if t.restrictions_json:
            try:
                blocked = json.loads(t.restrictions_json)
            except:
                blocked = []

        response.append(
            {"id": str(t.id), "name": t.name, "dept": "Кафедра", "blocked": blocked}
        )
    return response


@router.post("/teachers/{teacher_id}/restrictions")
async def update_teacher_restrictions(
    teacher_id: int,
    payload: TeacherRestrictionsModel,
    db: AsyncSession = Depends(async_get_db),
):
    stmt = select(Teacher).where(Teacher.id == teacher_id)
    result = await db.execute(stmt)
    teacher = result.scalar_one_or_none()

    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    teacher.restrictions_json = json.dumps(payload.restrictions.dict())
    await db.commit()
    return {"detail": "Restrictions updated"}


@router.get("/stats")
async def get_scheduler_stats(db: AsyncSession = Depends(async_get_db)):
    stmt_streams = select(func.count(Stream.id))
    result_streams = await db.execute(stmt_streams)
    total_streams = result_streams.scalar()

    stmt_ignored = select(func.count(Stream.id)).where(Stream.is_ignored == True)
    result_ignored = await db.execute(stmt_ignored)
    ignored_streams = result_ignored.scalar()

    stmt_groups = select(func.count(distinct(StreamGroup.group_name)))
    result_groups = await db.execute(stmt_groups)
    total_groups = result_groups.scalar()

    stmt_teachers = select(func.count(Teacher.id))
    result_teachers = await db.execute(stmt_teachers)
    total_teachers = result_teachers.scalar()

    return {
        "total_streams": total_streams,
        "active_streams": total_streams - ignored_streams,
        "ignored_streams": ignored_streams,
        "total_groups": total_groups,
        "total_teachers": total_teachers,
    }


# --- New functionality restored below ---


@router.get("/teachers/export")
async def export_teacher_availability(db: AsyncSession = Depends(async_get_db)):
    stmt = select(Teacher)
    result = await db.execute(stmt)
    teachers = result.scalars().all()

    data = []
    for t in teachers:
        import json

        try:
            res = (
                json.loads(t.restrictions_json)
                if t.restrictions_json
                else {"mode": "all", "recurring": [], "specific": []}
            )
        except:
            res = {"mode": "all", "recurring": [], "specific": []}

        data.append(
            {
                "ФИО преподавателя": t.name,
                "Режим": res.get("mode", "blacklist"),
                "Регулярные окна (День_Пара)": ",".join(res.get("recurring", [])),
                "Конкретные даты (ГГГГ-ММ-ДД_Пара)": ",".join(res.get("specific", [])),
            }
        )

    import io

    import pandas as pd
    from fastapi.responses import StreamingResponse

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Доступность")

    output.seek(0)

    headers = {
        "Content-Disposition": 'attachment; filename="teacher_availability.xlsx"'
    }
    return StreamingResponse(
        output,
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/teachers/import")
async def import_teacher_availability(
    file: UploadFile = File(...), db: AsyncSession = Depends(async_get_db)
):
    import io
    import json

    import pandas as pd

    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))

    updated_count = 0
    for _, row in df.iterrows():
        name = str(row["ФИО преподавателя"]).strip()
        mode = str(row["Режим"]).strip()
        recurring = str(row.get("Регулярные окна (День_Пара)", "")).strip()
        specific = str(row.get("Конкретные даты (ГГГГ-ММ-ДД_Пара)", "")).strip()

        if not name or name == "nan":
            continue

        # Parse strings to lists
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

        # Update in DB
        stmt = select(Teacher).filter(Teacher.name == name)
        res = await db.execute(stmt)
        teacher = res.scalar_one_or_none()

        if teacher:
            teacher.restrictions_json = json.dumps(restr)
            updated_count += 1

    await db.commit()
    return {"status": "ok", "updated_teachers": updated_count}


@router.post("/generate")
async def generate_schedule(
    task: GenerationTaskModel,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(async_get_db),
):
    # 1. Parse dates
    start_dt = (
        datetime.strptime(task.start_date, "%Y-%m-%d") if task.start_date else None
    )
    end_dt = datetime.strptime(task.end_date, "%Y-%m-%d") if task.end_date else None

    # 2. Create a task record
    new_task = GenerationTask(
        groups_json=json.dumps(task.groups),
        holidays_json=json.dumps(task.holidays),
        settings_json=json.dumps(task.settings or {}),
        start_date=start_dt,
        end_date=end_dt,
        status="pending",
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)

    # 3. Trigger background generation
    background_tasks.add_task(
        GenerationService.run_generation,
        new_task.id,
        task.groups,
        task.holidays,
        task.settings.get("enabled_types", []),
        task.start_date,
        task.end_date,
    )

    return {
        "status": "ok",
        "message": "Задача на генерацию запущена в фоновом режиме.",
        "task_id": new_task.id,
    }


@router.get("/export")
async def export_schedule(
    task_id: int | None = None, db: AsyncSession = Depends(async_get_db)
):
    output = await generate_excel_report(db, task_id)
    if not output:
        raise HTTPException(status_code=404, detail="No schedule found to export")

    filename = (
        f"schedule_export_{task_id}.xlsx" if task_id else "schedule_export_all.xlsx"
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        output,
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/tasks")
async def get_generation_tasks(db: AsyncSession = Depends(async_get_db)):
    stmt = select(GenerationTask).order_by(GenerationTask.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/schedule")
async def get_schedule(
    task_id: int | None = None,
    group_name: str | None = None,
    teacher_id: int | None = None,
    db: AsyncSession = Depends(async_get_db),
):
    stmt = select(ScheduleEntry).options(selectinload(ScheduleEntry.teacher))

    if task_id:
        stmt = stmt.where(ScheduleEntry.task_id == task_id)
    if group_name:
        stmt = stmt.where(ScheduleEntry.group_name == group_name)
    if teacher_id:
        stmt = stmt.where(ScheduleEntry.teacher_id == teacher_id)

    stmt = stmt.order_by(ScheduleEntry.date, ScheduleEntry.lesson_number)
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


async def refresh_task_warnings(task_id: int, db: AsyncSession):
    stmt = (
        select(ScheduleEntry)
        .options(selectinload(ScheduleEntry.teacher))
        .where(ScheduleEntry.task_id == task_id)
    )
    res = await db.execute(stmt)
    all_entries = res.scalars().all()

    by_slot: dict[tuple[str, int], list] = {}
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

    for (d, l), slot_entries in by_slot.items():
        for e1 in slot_entries:
            slot_warnings: list[str] = []

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
                    # Mon: (0+1)%7=1, Tue: (1+1)%7=2, ..., Sat: (5+1)%7=6, Sun: (6+1)%7=0
                    py_wd = e1.date.weekday() if hasattr(e1.date, "weekday") else -1
                    js_weekday = (py_wd + 1) % 7 if py_wd >= 0 else -1
                    lesson = e1.lesson_number
                    date_str = (
                        e1.date.strftime("%Y-%m-%d")
                        if hasattr(e1.date, "strftime")
                        else str(e1.date)
                    )

                    # Check recurring: format is "WEEKDAY-LESSON" e.g. "1-3" (Mon slot 3)
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
                            # Use rsplit to split off the last segment (lesson number)
                            # "2026-05-16-3" → ("2026-05-16", "3")
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
                        # In whitelist mode, only listed slots are ALLOWED
                        if not is_in_recurring and not is_in_specific:
                            is_blocked = True
                    else:  # blacklist
                        # In blacklist mode, listed slots are FORBIDDEN
                        if is_in_recurring or is_in_specific:
                            is_blocked = True

                    if is_blocked:
                        slot_warnings.append(
                            "Преподаватель недоступен по личному расписанию"
                        )
                except Exception as ex:
                    logger.error(
                        f"Error parsing restrictions for teacher {e1.teacher.name}: {ex}"
                    )

            e1.warning = "; ".join(slot_warnings) if slot_warnings else None


async def get_task_entries_json(task_id: int, db: AsyncSession):
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


@router.patch("/schedule/{entry_id}")
async def update_schedule_entry(
    entry_id: int,
    payload: ScheduleUpdateModel,
    db: AsyncSession = Depends(async_get_db),
):
    stmt = select(ScheduleEntry).where(ScheduleEntry.id == entry_id)
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Schedule entry not found")

    if payload.lesson_number is not None:
        entry.lesson_number = payload.lesson_number
    elif "lesson_number" in payload.model_fields_set:
        entry.lesson_number = None

    if payload.date is not None:
        try:
            entry.date = datetime.strptime(payload.date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
            )
    elif "date" in payload.model_fields_set:
        entry.date = None

    if payload.teacher_id is not None:
        entry.teacher_id = payload.teacher_id
    elif "teacher_id" in payload.model_fields_set:
        entry.teacher_id = None

    if payload.room_id is not None:
        entry.room_id = payload.room_id
    elif "room_id" in payload.model_fields_set:
        entry.room_id = None

    # --- Conflict Detection & Warning Refresh ---
    await refresh_task_warnings(entry.task_id, db)
    await db.commit()

    return {
        "detail": "Entry updated successfully",
        "entries": await get_task_entries_json(entry.task_id, db),
    }


@router.delete("/schedule/{entry_id}")
async def delete_schedule_entry(
    entry_id: int, db: AsyncSession = Depends(async_get_db)
):
    stmt = select(ScheduleEntry).where(ScheduleEntry.id == entry_id)
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Schedule entry not found")

    task_id = entry.task_id
    await db.delete(entry)
    await db.commit()

    entries = []
    if task_id:
        await refresh_task_warnings(task_id, db)
        await db.commit()
        entries = await get_task_entries_json(task_id, db)

    return {"detail": "Entry deleted successfully", "entries": entries}
