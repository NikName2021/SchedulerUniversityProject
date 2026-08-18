import io
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import pandas as pd
from core.config import (
    DEFAULT_COMPONENT_TIME_SECONDS,
    MAX_TIME_SECONDS,
    async_get_db,
)
from core.constants import (
    MAX_GENERATION_HORIZON_DAYS,
    NUM_WORKERS,
)
from database.all_models import (
    AvailabilityRule,
    FileType,
    GenerationComponent,
    GenerationIssue,
    GenerationLock,
    GenerationTask,
    ImportBatch,
    PlanningWeek,
    ScheduleEntry,
    Stream,
    StreamGroup,
    Teacher,
)
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from services.export_service import escape_excel_formula, generate_excel_report
from services.generation_lifecycle_service import (
    ACTIVE_STATUSES,
    GenerationLifecycleService,
)
from services.generation_service import GenerationService
from services.parser_service import parse_streams_content, read_tabular_content
from services.quality_service import ScheduleQualityService
from services.schedule_service import ScheduleService
from services.upload_service import read_upload_limited
from sqlalchemy import delete, distinct, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from worker import celery_app, generate_schedule_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SEMESTER_BATCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")


def _revoke_generation_workflow(task: GenerationTask) -> None:
    component_ids = json.loads(task.celery_component_ids_json or "[]")
    for celery_id in (
        task.celery_root_task_id,
        task.celery_workflow_id,
        *component_ids,
    ):
        if celery_id:
            try:
                celery_app.control.revoke(celery_id, terminate=True, signal="SIGTERM")
            except Exception:
                logger.exception("Failed to revoke Celery task %s", celery_id)


async def _delete_generation_tasks(
    tasks: list[GenerationTask], db: AsyncSession
) -> None:
    task_ids = [task.id for task in tasks]
    if not task_ids:
        return
    for task in tasks:
        if task.status in ACTIVE_STATUSES:
            _revoke_generation_workflow(task)

    await db.execute(
        update(GenerationTask)
        .where(GenerationTask.parent_task_id.in_(task_ids))
        .values(parent_task_id=None)
    )
    await db.execute(delete(ScheduleEntry).where(ScheduleEntry.task_id.in_(task_ids)))
    await db.execute(
        delete(GenerationIssue).where(GenerationIssue.task_id.in_(task_ids))
    )
    await db.execute(
        delete(GenerationComponent).where(GenerationComponent.task_id.in_(task_ids))
    )
    await db.execute(
        delete(GenerationLock).where(GenerationLock.task_id.in_(task_ids))
    )
    await db.execute(delete(GenerationTask).where(GenerationTask.id.in_(task_ids)))
    await db.commit()


class StreamUpdateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stream_type: str | None = Field(default=None, min_length=1, max_length=100)
    is_ignored: bool | None = None


class TimeIntervalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default="", max_length=100)
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")
    type: Literal["recurring", "specific"]
    day: int | None = Field(default=None, ge=0, le=6)
    date: str | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> "TimeIntervalModel":
        try:
            start = datetime.strptime(self.start, "%H:%M").time()
            end = datetime.strptime(self.end, "%H:%M").time()
        except ValueError as exc:
            raise ValueError("Interval times must use HH:MM") from exc
        if end <= start:
            raise ValueError("Interval end must be later than start")
        if self.type == "recurring" and self.day is None:
            raise ValueError("day is required for a recurring interval")
        if self.type == "specific":
            if self.date is None:
                raise ValueError("date is required for a specific interval")
            try:
                datetime.strptime(self.date, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("Interval date must use YYYY-MM-DD") from exc
        return self


class TeacherRestrictionsDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["blacklist", "whitelist"]
    specific: list[str] = Field(default_factory=list, max_length=5_000)
    recurring: list[str] = Field(default_factory=list, max_length=500)
    intervals: list[TimeIntervalModel] = Field(default_factory=list, max_length=500)

    @field_validator("recurring")
    @classmethod
    def validate_recurring(cls, values: list[str]) -> list[str]:
        for value in values:
            match = re.fullmatch(r"([0-6])-([1-7])", value)
            if match is None:
                raise ValueError(f"Invalid recurring restriction: {value}")
        return list(dict.fromkeys(values))

    @field_validator("specific")
    @classmethod
    def validate_specific(cls, values: list[str]) -> list[str]:
        for value in values:
            try:
                date_string, lesson = value.rsplit("-", 1)
                datetime.strptime(date_string, "%Y-%m-%d")
                if int(lesson) not in range(1, 8):
                    raise ValueError
            except ValueError as exc:
                raise ValueError(f"Invalid specific restriction: {value}") from exc
        return list(dict.fromkeys(values))


class TeacherRestrictionsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restrictions: TeacherRestrictionsDetails


class GenerationSettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled_types: list[str] = Field(default_factory=list, max_length=20)
    priorities: dict[str, Literal["morning", "day", "evening"]] = Field(
        default_factory=dict
    )
    rule_profile_id: int | None = Field(default=None, ge=1)
    created_at: datetime | None = None
    semester_period_id: int | None = Field(default=None, ge=1)
    base_task_id: int | None = Field(default=None, ge=1)
    affected_stream_ids: list[int] = Field(default_factory=list, max_length=10_000)
    max_total_events: int = Field(default=20_000, ge=1, le=20_000)
    max_component_events: int = Field(default=2_000, ge=1, le=2_000)
    max_component_seconds: int = Field(
        default=DEFAULT_COMPONENT_TIME_SECONDS, ge=5, le=MAX_TIME_SECONDS
    )
    solver_workers: int = Field(default=1, ge=1, le=NUM_WORKERS)
    room_assignment_max_seconds: int = Field(default=5, ge=1, le=60)


class GenerationTaskModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groups: list[str] = Field(min_length=1, max_length=1_000)
    holidays: list[str] = Field(default_factory=list, max_length=366)
    planning_week_id: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    settings: GenerationSettingsModel | None = None
    semester_batch_id: str | None = Field(default=None, max_length=100)

    @field_validator("groups")
    @classmethod
    def validate_groups(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 255 for value in cleaned):
            raise ValueError("Group names must contain 1 to 255 characters")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Group names must be unique")
        return cleaned

    @field_validator("holidays")
    @classmethod
    def validate_holidays(cls, values: list[str]) -> list[str]:
        for value in values:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("Holidays must use YYYY-MM-DD") from exc
        return list(dict.fromkeys(values))

    @field_validator("semester_batch_id")
    @classmethod
    def validate_batch_id(cls, value: str | None) -> str | None:
        if value is not None and SEMESTER_BATCH_PATTERN.fullmatch(value) is None:
            raise ValueError("Invalid semester_batch_id")
        return value


async def _resolve_generation_period(
    task: GenerationTaskModel, db: AsyncSession
) -> tuple[datetime | None, datetime | None]:
    start_date = task.start_date
    end_date = task.end_date
    if task.planning_week_id is not None:
        planning_week = await db.get(PlanningWeek, task.planning_week_id)
        if planning_week is None:
            raise HTTPException(status_code=404, detail="Planning week not found")
        start_date = planning_week.starts_on.isoformat()
        end_date = planning_week.ends_on.isoformat()

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Dates must use YYYY-MM-DD"
        ) from exc
    if start_dt and end_dt and end_dt < start_dt:
        raise HTTPException(
            status_code=422, detail="end_date must not precede start_date"
        )
    if (
        task.planning_week_id is None
        and start_dt
        and end_dt
        and (end_dt - start_dt).days + 1 > MAX_GENERATION_HORIZON_DAYS
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Период генерации не должен превышать "
                f"{MAX_GENERATION_HORIZON_DAYS} дней. Для разных недель "
                "создавайте отдельные недельные расчеты."
            ),
        )
    return start_dt, end_dt


class ScheduleUpdateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson_number: int | None = Field(default=None, ge=1, le=7)
    date: str | None = None
    teacher_id: int | None = Field(default=None, ge=1)
    room_id: str | None = Field(default=None, min_length=1, max_length=100)
    apply_to_stream: bool | None = None
    is_locked: bool | None = None


@router.post("/import/streams")
async def import_streams(
    file: UploadFile = File(...), db: AsyncSession = Depends(async_get_db)
):
    content, safe_filename = await read_upload_limited(
        file, allowed_extensions={".xls", ".xlsx", ".csv"}
    )

    try:
        parsed_data = parse_streams_content(content, safe_filename)
    except (ValueError, TypeError, pd.errors.ParserError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Error parsing file: {str(exc)}"
        ) from exc

    if not parsed_data:
        raise HTTPException(status_code=400, detail="No streams found in the document")

    # Save file to disk
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = Path(safe_filename).suffix.lower()
    unique_filename = f"{timestamp}_{uuid.uuid4().hex[:12]}{extension}"
    file_path = UPLOAD_DIR / unique_filename

    try:
        file_path.write_bytes(content)

        batch = ImportBatch(
            filename=safe_filename,
            file_path=str(file_path),
            file_type=FileType.STREAMS,
            status="completed",
        )
        db.add(batch)
        await db.flush()

        res = await ScheduleService.import_streams(parsed_data, batch.id, db)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409, detail="Imported data conflicts with existing records"
        ) from exc
    except Exception:
        await db.rollback()
        file_path.unlink(missing_ok=True)
        raise

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

    if batch.file_path:
        try:
            candidate = Path(batch.file_path).resolve()
            if candidate.is_relative_to(UPLOAD_DIR.resolve()) and candidate.is_file():
                candidate.unlink()
            elif candidate.exists():
                logger.warning(
                    "Refused to delete import file outside upload directory: %s",
                    candidate,
                )
        except OSError as e:
            logger.error("Error deleting file %s: %s", batch.file_path, e)

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
    except Exception:
        logger.exception("Error getting subjects summary")
        raise HTTPException(
            status_code=500,
            detail="Unable to build subjects summary",
        ) from None


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
    await db.execute(
        delete(AvailabilityRule).where(AvailabilityRule.teacher_id == teacher_id)
    )
    rule_kind = (
        "available" if payload.restrictions.mode == "whitelist" else "unavailable"
    )
    structured_rules: list[AvailabilityRule] = []
    for raw_value in payload.restrictions.recurring:
        try:
            js_day, lesson = raw_value.split("-", 1)
            structured_rules.append(
                AvailabilityRule(
                    teacher_id=teacher_id,
                    rule_kind=rule_kind,
                    recurrence="weekly",
                    weekday=(int(js_day) - 1) % 7,
                    lesson_start=int(lesson),
                    lesson_end=int(lesson),
                    is_hard=True,
                )
            )
        except ValueError:
            continue
    for raw_value in payload.restrictions.specific:
        try:
            date_string, lesson = raw_value.rsplit("-", 1)
            structured_rules.append(
                AvailabilityRule(
                    teacher_id=teacher_id,
                    rule_kind=rule_kind,
                    recurrence="specific",
                    specific_date=datetime.strptime(date_string, "%Y-%m-%d").date(),
                    lesson_start=int(lesson),
                    lesson_end=int(lesson),
                    is_hard=True,
                )
            )
        except ValueError:
            continue
    db.add_all(structured_rules)
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
                "ФИО преподавателя": escape_excel_formula(t.name),
                "Режим": res.get("mode", "blacklist"),
                "Регулярные окна (День_Пара)": escape_excel_formula(
                    ",".join(res.get("recurring", []))
                ),
                "Конкретные даты (ГГГГ-ММ-ДД_Пара)": escape_excel_formula(
                    ",".join(res.get("specific", []))
                ),
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
    content, filename = await read_upload_limited(
        file, allowed_extensions={".xls", ".xlsx", ".csv"}
    )
    try:
        df = read_tabular_content(content, filename)
        required_columns = {"ФИО преподавателя", "Режим"}
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Missing required columns: {missing}")
    except (ValueError, TypeError, pd.errors.ParserError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Error parsing file: {str(exc)}"
        ) from exc

    try:
        updated_count = await ScheduleService.import_teacher_availability(df, db)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail=f"Error parsing file: {str(exc)}"
        ) from exc
    return {"status": "ok", "updated_teachers": updated_count}


@router.post("/generate")
async def generate_schedule(
    task: GenerationTaskModel,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> JSONResponse:
    start_dt, end_dt = await _resolve_generation_period(task, db)
    start_date = start_dt.date().isoformat() if start_dt else None
    end_date = end_dt.date().isoformat() if end_dt else None
    settings = (
        task.settings.model_dump(mode="json", exclude_none=True)
        if task.settings is not None
        else {}
    )
    try:
        new_task = await GenerationLifecycleService.reserve_task(
            db,
            groups=task.groups,
            holidays=task.holidays,
            settings=settings,
            planning_week_id=task.planning_week_id,
            start_date=start_dt,
            end_date=end_dt,
            semester_batch_id=task.semester_batch_id,
        )
    except (RuntimeError, IntegrityError) as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # 3. Enqueue durable background generation
    try:
        async_result = generate_schedule_task.delay(
            new_task.id,
            task.groups,
            task.holidays,
            settings.get("enabled_types", []),
            start_date,
            end_date,
            task.planning_week_id,
        )
        new_task.celery_root_task_id = async_result.id
        await db.commit()
    except Exception as exc:
        new_task.status = "failed"
        new_task.error_message = "Generation queue is unavailable"
        await GenerationLifecycleService.release_locks(new_task.id, db)
        await db.commit()
        logger.exception("Failed to enqueue generation task %s", new_task.id)
        raise HTTPException(
            status_code=503,
            detail="Generation queue is unavailable",
        ) from exc

    return {
        "status": "ok",
        "message": "Задача на генерацию запущена в фоновом режиме.",
        "task_id": new_task.id,
    }


@router.get("/export")
async def export_schedule(
    task_id: int | None = None,
    semester_batch_id: str | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> StreamingResponse:
    if (
        semester_batch_id is not None
        and SEMESTER_BATCH_PATTERN.fullmatch(semester_batch_id) is None
    ):
        raise HTTPException(status_code=422, detail="Invalid semester_batch_id")
    output = await generate_excel_report(db, task_id, semester_batch_id)
    if not output:
        raise HTTPException(status_code=404, detail="No schedule found to export")

    filename = (
        f"schedule_export_semester_{semester_batch_id}.xlsx"
        if semester_batch_id
        else f"schedule_export_{task_id}.xlsx"
        if task_id
        else "schedule_export_all.xlsx"
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
    stmt = (
        select(GenerationTask)
        .options(
            selectinload(GenerationTask.planning_week).selectinload(
                PlanningWeek.period
            ),
        )
        .order_by(GenerationTask.created_at.desc())
    )
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
            "planning_week_id": t.planning_week_id,
            "semester_batch_id": t.semester_batch_id,
            "planning_week": (
                {
                    "id": t.planning_week.id,
                    "sequence_number": t.planning_week.sequence_number,
                    "starts_on": t.planning_week.starts_on.isoformat(),
                    "ends_on": t.planning_week.ends_on.isoformat(),
                    "period_id": t.planning_week.period_id,
                    "period_name": t.planning_week.period.name
                    if t.planning_week.period
                    else None,
                }
                if t.planning_week
                else None
            ),
            "total_components": t.total_components,
            "completed_components": t.completed_components,
            "progress_percent": t.progress_percent,
            "metrics": json.loads(t.metrics_json) if t.metrics_json else {},
            "celery_workflow_id": t.celery_workflow_id,
            "celery_root_task_id": t.celery_root_task_id,
            "celery_component_ids": (
                json.loads(t.celery_component_ids_json)
                if t.celery_component_ids_json
                else []
            ),
            "parent_task_id": t.parent_task_id,
            "version_number": t.version_number,
            "publication_status": t.publication_status,
            "published_at": t.published_at.isoformat() if t.published_at else None,
            "canceled_at": t.canceled_at.isoformat() if t.canceled_at else None,
            "edit_revision": t.edit_revision,
        }
        for t in tasks
    ]


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_generation_task(
    task_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> Response:
    task = await db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Generation task not found")
    await _delete_generation_tasks([task], db)
    return Response(status_code=204)


@router.delete("/semester-batches/{semester_batch_id}", status_code=204)
async def delete_semester_batch(
    semester_batch_id: str,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> Response:
    if SEMESTER_BATCH_PATTERN.fullmatch(semester_batch_id) is None:
        raise HTTPException(status_code=422, detail="Invalid semester_batch_id")
    result = await db.execute(
        select(GenerationTask).where(
            GenerationTask.semester_batch_id == semester_batch_id
        )
    )
    tasks = list(result.scalars())
    if not tasks:
        raise HTTPException(status_code=404, detail="Semester batch not found")
    await _delete_generation_tasks(tasks, db)
    return Response(status_code=204)


@router.post("/tasks/{task_id}/cancel")
async def cancel_generation_task(
    task_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> dict[str, Any]:
    task = await db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Generation task not found")
    if task.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Generation task is not active")
    _revoke_generation_workflow(task)
    task.status = "canceled"
    task.canceled_at = datetime.utcnow()
    task.error_message = "Generation canceled by operator"
    task.progress_percent = 100
    await GenerationLifecycleService.release_locks(task.id, db)
    await db.commit()
    return {"status": task.status, "task_id": task.id}


@router.post("/tasks/{task_id}/retry", status_code=202)
async def retry_generation_task(
    task_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> dict[str, Any]:
    source = await db.get(GenerationTask, task_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Generation task not found")
    if source.status in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="Generation task is still active")
    groups = json.loads(source.groups_json or "[]")
    holidays = json.loads(source.holidays_json or "[]")
    settings = json.loads(source.settings_json or "{}")
    try:
        retry_task = await GenerationLifecycleService.reserve_task(
            db,
            groups=groups,
            holidays=holidays,
            settings=settings,
            planning_week_id=source.planning_week_id,
            start_date=source.start_date,
            end_date=source.end_date,
            parent_task_id=source.id,
            semester_batch_id=source.semester_batch_id,
        )
        async_result = generate_schedule_task.delay(
            retry_task.id,
            groups,
            holidays,
            settings.get("enabled_types", []),
            retry_task.start_date.date().isoformat() if retry_task.start_date else None,
            retry_task.end_date.date().isoformat() if retry_task.end_date else None,
            retry_task.planning_week_id,
        )
        retry_task.celery_root_task_id = async_result.id
        await db.commit()
    except (RuntimeError, IntegrityError) as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        retry_task.status = "failed"
        retry_task.error_message = "Generation queue is unavailable"
        await GenerationLifecycleService.release_locks(retry_task.id, db)
        await db.commit()
        raise HTTPException(
            status_code=503, detail="Generation queue is unavailable"
        ) from exc
    return {"status": "queued", "task_id": retry_task.id}


@router.post("/tasks/{task_id}/publish")
async def publish_schedule_version(
    task_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> dict[str, Any]:
    task = await db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Generation task not found")
    try:
        await GenerationLifecycleService.publish(task, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"task_id": task.id, "publication_status": task.publication_status}


@router.post("/tasks/{task_id}/archive")
async def archive_schedule_version(
    task_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> dict[str, Any]:
    task = await db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Generation task not found")
    try:
        await GenerationLifecycleService.archive(task, db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"task_id": task.id, "publication_status": task.publication_status}


@router.get("/tasks/{task_id}/diagnostics")
async def get_generation_diagnostics(
    task_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> dict[str, Any]:
    if await db.get(GenerationTask, task_id) is None:
        raise HTTPException(status_code=404, detail="Generation task not found")
    return await GenerationLifecycleService.diagnostics(task_id, db)


@router.get("/tasks/{task_id}/components")
async def get_generation_components(
    task_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> list[dict[str, Any]]:
    task = await db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Generation task not found")
    result = await db.execute(
        select(GenerationComponent)
        .where(GenerationComponent.task_id == task_id)
        .order_by(GenerationComponent.component_key)
    )
    return [
        {
            "id": component.id,
            "component_key": component.component_key,
            "status": component.status,
            "event_count": component.event_count,
            "variable_count": component.variable_count,
            "constraint_count": component.constraint_count,
            "solve_seconds": component.solve_seconds,
            "objective": component.objective,
            "error_message": component.error_message,
        }
        for component in result.scalars()
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
    semester_batch_id: str | None = None,
    group_name: str | None = None,
    teacher_id: int | None = None,
    db: Annotated[AsyncSession, Depends(async_get_db)] = None,
) -> list[dict[str, Any]]:
    stmt = select(ScheduleEntry).options(selectinload(ScheduleEntry.teacher))

    if task_id is not None:
        stmt = stmt.where(ScheduleEntry.task_id == task_id)
    if semester_batch_id is not None:
        stmt = stmt.join(
            GenerationTask, GenerationTask.id == ScheduleEntry.task_id
        ).where(GenerationTask.semester_batch_id == semester_batch_id)
    if group_name is not None:
        stmt = stmt.where(ScheduleEntry.group_name == group_name)
    if teacher_id is not None:
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
            "is_locked": e.is_locked,
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
    task = await db.get(GenerationTask, entry.task_id)
    if task and task.publication_status == "published":
        raise HTTPException(status_code=409, detail="Published schedules are read-only")

    source_task = task
    target_task = task
    target_date: datetime | None = None
    if payload.date is not None:
        try:
            target_date = datetime.strptime(payload.date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
            ) from None

        outside_source_period = bool(
            task
            and (
                (task.start_date and target_date < task.start_date)
                or (task.end_date and target_date > task.end_date)
            )
        )
        if outside_source_period:
            if not task or not task.semester_batch_id:
                raise HTTPException(
                    status_code=422,
                    detail="Дата занятия находится за пределами периода расчёта",
                )
            target_task = await db.scalar(
                select(GenerationTask)
                .where(
                    GenerationTask.semester_batch_id == task.semester_batch_id,
                    GenerationTask.start_date <= target_date,
                    GenerationTask.end_date >= target_date,
                    GenerationTask.status.in_(["success", "partial"]),
                    GenerationTask.publication_status != "archived",
                )
                .order_by(
                    GenerationTask.version_number.desc(),
                    GenerationTask.created_at.desc(),
                )
                .limit(1)
            )
            if target_task is None:
                raise HTTPException(
                    status_code=422,
                    detail="Для выбранной недели нет завершённого расчёта",
                )
            if target_task.publication_status == "published":
                raise HTTPException(
                    status_code=409, detail="Published schedules are read-only"
                )

    entries_to_update = [entry]

    is_lecture = entry.stream_type and "лекция" in entry.stream_type.lower()
    is_extracur = entry.stream_type and "внеучебное" in entry.stream_type.lower()

    if is_lecture or (is_extracur and payload.apply_to_stream):
        date_cond = (
            ScheduleEntry.date == entry.date
            if entry.date is not None
            else ScheduleEntry.date.is_(None)
        )
        lesson_cond = (
            ScheduleEntry.lesson_number == entry.lesson_number
            if entry.lesson_number is not None
            else ScheduleEntry.lesson_number.is_(None)
        )
        teacher_cond = (
            ScheduleEntry.teacher_id == entry.teacher_id
            if entry.teacher_id is not None
            else ScheduleEntry.teacher_id.is_(None)
        )

        stmt_related = select(ScheduleEntry).where(
            ScheduleEntry.task_id == entry.task_id,
            ScheduleEntry.event_name == entry.event_name,
            ScheduleEntry.stream_type == entry.stream_type,
            teacher_cond,
            date_cond,
            lesson_cond,
            ScheduleEntry.id != entry.id,
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
            e.date = target_date
            if target_task and target_task.id != e.task_id:
                e.task_id = target_task.id
                e.planning_week_id = target_task.planning_week_id
        elif "date" in payload.model_fields_set:
            e.date = None

        if payload.teacher_id is not None:
            if await db.get(Teacher, payload.teacher_id) is None:
                raise HTTPException(status_code=404, detail="Teacher not found")
            e.teacher_id = payload.teacher_id
        elif "teacher_id" in payload.model_fields_set:
            e.teacher_id = None

        if payload.room_id is not None:
            try:
                room = await ScheduleService.resolve_room(payload.room_id, db)
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            e.room_id = payload.room_id
            e.room_ref_id = room.id if room else None
        elif "room_id" in payload.model_fields_set:
            e.room_id = None
            e.room_ref_id = None

        if payload.is_locked is not None:
            e.is_locked = payload.is_locked

    await db.flush()
    conflicts = await ScheduleService.validate_manual_changes(
        target_task.id if target_task else entry.task_id,
        {item.id for item in entries_to_update},
        db,
    )
    if conflicts:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"message": "Изменение создает конфликт", "conflicts": conflicts},
        )

    # --- Conflict Detection & Warning Refresh ---
    affected_task_ids = {
        task_id
        for task_id in (
            source_task.id if source_task else None,
            target_task.id if target_task else None,
        )
        if task_id is not None
    }
    for affected_task_id in affected_task_ids:
        await ScheduleService.refresh_task_warnings(affected_task_id, db)
    if source_task:
        source_task.edit_revision += 1
    if target_task and target_task is not source_task:
        target_task.edit_revision += 1
    await db.commit()

    if source_task and source_task.semester_batch_id:
        updated_entries = await get_schedule(
            semester_batch_id=source_task.semester_batch_id,
            db=db,
        )
    else:
        updated_entries = await ScheduleService.get_task_entries_json(
            entry.task_id, db
        )
    return {
        "detail": "Entry updated successfully",
        "entries": updated_entries,
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
    task = await db.get(GenerationTask, entry.task_id)
    if task and task.publication_status == "published":
        raise HTTPException(status_code=409, detail="Published schedules are read-only")
    if entry.is_locked:
        raise HTTPException(
            status_code=409, detail="Locked entries must be unlocked before deletion"
        )

    task_id = entry.task_id
    await db.delete(entry)
    if task:
        task.edit_revision += 1
    await db.commit()

    entries = []
    if task_id:
        await ScheduleService.refresh_task_warnings(task_id, db)
        await db.commit()
        entries = await ScheduleService.get_task_entries_json(task_id, db)

    return {"detail": "Entry deleted successfully", "entries": entries}
