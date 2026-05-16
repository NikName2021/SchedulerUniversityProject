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

    # --- Conflict Detection ---
    # 1. Clear current warning
    entry.warning = None

    # 2. Check for overlaps in the same task
    # We check: teacher, room, and group (though group is mostly handled by UI grid structure)
    conflicts_stmt = select(ScheduleEntry).where(
        ScheduleEntry.task_id == entry.task_id,
        ScheduleEntry.date == entry.date,
        ScheduleEntry.lesson_number == entry.lesson_number,
        ScheduleEntry.id != entry.id,
    )
    result = await db.execute(conflicts_stmt)
    other_entries = result.scalars().all()

    warnings = []
    for other in other_entries:
        if entry.teacher_id and entry.teacher_id == other.teacher_id:
            warnings.append(f"Преподаватель занят: {other.event_name}")
        if entry.room_id and entry.room_id == other.room_id:
            warnings.append(f"Аудитория занята: {other.event_name}")
        if entry.group_name == other.group_name:
            warnings.append(f"У группы {entry.group_name} уже есть пара")

    if warnings:
        entry.warning = "; ".join(warnings)

    # --- Side Effect: Recalculate warnings for others ---
    # If we moved AWAY from a conflict, the other entry might now be clean.
    # For simplicity in MVP, we just commit here.
    # A full consistency check would re-scan all entries in the task.

    await db.commit()
    return {"detail": "Entry updated successfully", "warning": entry.warning}


@router.delete("/schedule/{entry_id}")
async def delete_schedule_entry(
    entry_id: int, db: AsyncSession = Depends(async_get_db)
):
    stmt = select(ScheduleEntry).where(ScheduleEntry.id == entry_id)
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Schedule entry not found")

    await db.delete(entry)
    await db.commit()
    return {"detail": "Entry deleted successfully"}
