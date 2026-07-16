import io
import json
import logging
import os
import uuid

import pandas as pd
from datetime import datetime
from typing import Annotated, Any

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
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from services.export_service import generate_excel_report
from services.generation_service import GenerationService
from services.parser_service import parse_streams_content
from services.quality_service import ScheduleQualityService
from services.schedule_service import ScheduleService
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


class TimeIntervalModel(BaseModel):
    id: str = ""
    start: str  # "HH:MM"
    end: str  # "HH:MM"
    type: str  # "recurring" | "specific"
    day: int | None = None  # JS weekday for recurring
    date: str | None = None  # "YYYY-MM-DD" for specific


class TeacherRestrictionsDetails(BaseModel):
    mode: str
    specific: list[str]
    recurring: list[str]
    intervals: list[TimeIntervalModel] = []


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
    apply_to_stream: bool | None = None


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

    res = await ScheduleService.import_streams(parsed_data, batch.id, db)
    await db.commit()

    return {
        "detail": "Success",
        "batch_id": batch.id,
        "streams_added": res["streams_added"],
        "groups_added": res["groups_added"],
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
async def get_groups(
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> dict[str, Any]:
    stmt = select(distinct(StreamGroup.group_name)).order_by(StreamGroup.group_name)
    result = await db.execute(stmt)
    groups = result.scalars().all()
    return {"groups": groups}


@router.get("/subjects-summary")
async def get_subjects_summary(
    groups: Annotated[str, Query(...)] = None,  # Comma separated
    types: Annotated[str, Query(...)] = None,  # Comma separated
) -> dict[str, list[str]]:
    selected_groups = groups.split(",")
    enabled_types = types.split(",")
    try:

        summary = await GenerationService.get_subjects_summary(
            selected_groups, enabled_types
        )
        return summary
    except Exception as e:
        logger.error(f"Error getting subjects summary: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.get("/streams")
async def get_streams_by_group(
    group_name: Annotated[str, Query(..., description="Group name filter")] = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> list[dict[str, Any]]:
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
    stream_id: int,
    payload: StreamUpdateModel,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> JSONResponse:
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
async def get_teachers(
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> list[dict[str, Any]]:
    stmt = select(Teacher).order_by(Teacher.name)
    result = await db.execute(stmt)
    teachers = result.scalars().all()

    response = []
    for t in teachers:
        blocked = []
        if t.restrictions_json:
            try:
                blocked = json.loads(t.restrictions_json)
            except Exception:
                blocked = []

        response.append(
            {"id": str(t.id), "name": t.name, "dept": "Кафедра", "blocked": blocked}
        )
    return response


@router.post("/teachers/{teacher_id}/restrictions")
async def update_teacher_restrictions(
    teacher_id: int,
    payload: TeacherRestrictionsModel,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> JSONResponse:
    stmt = select(Teacher).where(Teacher.id == teacher_id)
    result = await db.execute(stmt)
    teacher = result.scalar_one_or_none()

    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    teacher.restrictions_json = json.dumps(payload.restrictions.model_dump())
    await db.commit()
    return {"detail": "Restrictions updated"}


@router.get("/stats")
async def get_scheduler_stats(
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> dict[str, Any]:
    stmt_streams = select(func.count(Stream.id))
    result_streams = await db.execute(stmt_streams)
    total_streams = result_streams.scalar()

    stmt_ignored = select(func.count(Stream.id)).where(Stream.is_ignored)
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
async def export_teacher_availability(
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> StreamingResponse:
    stmt = select(Teacher)
    result = await db.execute(stmt)
    teachers = result.scalars().all()

    data = []
    for t in teachers:

        try:
            res = (
                json.loads(t.restrictions_json)
                if t.restrictions_json
                else {"mode": "all", "recurring": [], "specific": []}
            )
        except Exception:
            res = {"mode": "all", "recurring": [], "specific": []}

        data.append(
            {
                "ФИО преподавателя": t.name,
                "Режим": res.get("mode", "blacklist"),
                "Регулярные окна (День_Пара)": ",".join(res.get("recurring", [])),
                "Конкретные даты (ГГГГ-ММ-ДД_Пара)": ",".join(res.get("specific", [])),
            }
        )


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
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> JSONResponse:

    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))

    updated_count = await ScheduleService.import_teacher_availability(df, db)
    await db.commit()
    return {"status": "ok", "updated_teachers": updated_count}


@router.post("/generate")
async def generate_schedule(
    task: GenerationTaskModel,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> JSONResponse:
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
    task_id: int | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> StreamingResponse:
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
async def get_generation_tasks(
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> list[dict[str, Any]]:
    stmt = select(GenerationTask).order_by(GenerationTask.created_at.desc())
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [
        {
            "id": t.id,
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "start_date": t.start_date.isoformat() if t.start_date else None,
            "end_date": t.end_date.isoformat() if t.end_date else None,
            "groups": json.loads(t.groups_json) if t.groups_json else [],
            "holidays": json.loads(t.holidays_json) if t.holidays_json else [],
            "settings": json.loads(t.settings_json) if t.settings_json else {},
            "result_count": t.result_count,
            "error_message": t.error_message,
        }
        for t in tasks
    ]


@router.get("/schedule/quality")
async def get_schedule_quality(
    task_id: Annotated[int, Query(...)],
    group_name: Annotated[str, Query(...)],
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> dict[str, Any]:
    return await ScheduleQualityService.analyze(task_id, group_name, db)


@router.get("/schedule")
async def get_schedule(
    task_id: int | None = None,
    group_name: str | None = None,
    teacher_id: int | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> list[dict[str, Any]]:
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


@router.patch("/schedule/{entry_id}")
async def update_schedule_entry(
    entry_id: int,
    payload: ScheduleUpdateModel,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> JSONResponse:
    stmt = select(ScheduleEntry).where(ScheduleEntry.id == entry_id)
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Schedule entry not found")

    entries_to_update = [entry]
    
    is_lecture = entry.stream_type and "лекция" in entry.stream_type.lower()
    is_extracur = entry.stream_type and "внеучебное" in entry.stream_type.lower()
    
    if is_lecture or (is_extracur and payload.apply_to_stream):
        date_cond = ScheduleEntry.date == entry.date if entry.date is not None else ScheduleEntry.date.is_(None)
        lesson_cond = ScheduleEntry.lesson_number == entry.lesson_number if entry.lesson_number is not None else ScheduleEntry.lesson_number.is_(None)
        teacher_cond = ScheduleEntry.teacher_id == entry.teacher_id if entry.teacher_id is not None else ScheduleEntry.teacher_id.is_(None)
        
        stmt_related = select(ScheduleEntry).where(
            ScheduleEntry.task_id == entry.task_id,
            ScheduleEntry.event_name == entry.event_name,
            ScheduleEntry.stream_type == entry.stream_type,
            teacher_cond,
            date_cond,
            lesson_cond,
            ScheduleEntry.id != entry.id
        )
        res_related = await db.execute(stmt_related)
        related_all = res_related.scalars().all()
        
        seen_groups = {entry.group_name}
        for r in related_all:
            if r.group_name not in seen_groups:
                entries_to_update.append(r)
                seen_groups.add(r.group_name)

    for e in entries_to_update:
        if payload.lesson_number is not None:
            e.lesson_number = payload.lesson_number
        elif "lesson_number" in payload.model_fields_set:
            e.lesson_number = None

        if payload.date is not None:
            try:
                e.date = datetime.strptime(payload.date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
                ) from None
        elif "date" in payload.model_fields_set:
            e.date = None

        if payload.teacher_id is not None:
            e.teacher_id = payload.teacher_id
        elif "teacher_id" in payload.model_fields_set:
            e.teacher_id = None

        if payload.room_id is not None:
            e.room_id = payload.room_id
        elif "room_id" in payload.model_fields_set:
            e.room_id = None

    # --- Conflict Detection & Warning Refresh ---
    await ScheduleService.refresh_task_warnings(entry.task_id, db)
    await db.commit()

    return {
        "detail": "Entry updated successfully",
        "entries": await ScheduleService.get_task_entries_json(entry.task_id, db),
    }


@router.delete("/schedule/{entry_id}")
async def delete_schedule_entry(
    entry_id: int, db: Annotated[AsyncSession, Depends(async_get_db)] = None
) -> JSONResponse:
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
        await ScheduleService.refresh_task_warnings(task_id, db)
        await db.commit()
        entries = await ScheduleService.get_task_entries_json(task_id, db)

    return {"detail": "Entry deleted successfully", "entries": entries}
