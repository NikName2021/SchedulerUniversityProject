import tempfile
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import distinct, func

from core.config import async_get_db
from database.all_models import ImportBatch, FileType, Teacher, Stream, StreamGroup
from services.parser_service import parse_streams_content

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

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
    settings: dict | None = None

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "../../uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/import/streams")
async def import_streams(file: UploadFile = File(...), db: AsyncSession = Depends(async_get_db)):
    if not file.filename.endswith((".xls", ".xlsx", ".csv")):
        raise HTTPException(status_code=400, detail="Invalid file type")

    # Read bytes
    file_bytes = await file.read()
    
    # Parse streams
    try:
        parsed_data = parse_streams_content(file_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing file: {str(e)}")
        
    if not parsed_data:
        raise HTTPException(status_code=400, detail="No streams found in the document")

    # Save file to disk
    timestamp = datetime.now().strftime("%Y%md_%H%M%S")
    unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Create ImportBatch
    batch = ImportBatch(filename=file.filename, file_path=file_path, file_type=FileType.STREAMS)
    db.add(batch)
    await db.flush() # To get batch.id
    
    # Track teachers to avoid duplicates in the same batch, and potentially across batches
    # Simplification: we create a new teacher if not exists by name
    added_streams_count = 0
    added_groups_count = 0
    
    for stream_data in parsed_data:
        teacher_clean = stream_data["teacher"]
        teacher_id = None
        
        if teacher_clean:
            # Check if teacher exists
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
                
        # Create Stream
        new_stream = Stream(
            import_batch_id=batch.id,
            teacher_id=teacher_id,
            event_name=stream_data["event"],
            stream_type=stream_data["type"]
        )
        db.add(new_stream)
        await db.flush()
        added_streams_count += 1
        
        # Create groups
        for group in stream_data["groups"]:
            new_group = StreamGroup(
                stream_id=new_stream.id,
                group_name=group["name"],
                group_size=group["size"]
            )
            db.add(new_group)
            added_groups_count += 1

    await db.commit()
    
    return {
        "detail": "Success",
        "batch_id": batch.id,
        "streams_added": added_streams_count,
        "groups_added": added_groups_count
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
            "created_date": b.created_date
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
        
    # Delete physical file
    if batch.file_path and os.path.exists(batch.file_path):
        try:
            os.remove(batch.file_path)
        except OSError as e:
            print(f"Error deleting file {batch.file_path}: {e}")
            
    await db.delete(batch)
    await db.commit()
    
    return {"detail": "Import batch and associated data deleted"}

@router.get("/groups")
async def get_groups(db: AsyncSession = Depends(async_get_db)):
    # Returns unique group names ordered alphabetically
    stmt = select(distinct(StreamGroup.group_name)).order_by(StreamGroup.group_name)
    result = await db.execute(stmt)
    groups = result.scalars().all()
    return {"groups": groups}

@router.get("/streams")
async def get_streams_by_group(group_name: str = Query(..., description="Group name filter"), db: AsyncSession = Depends(async_get_db)):
    # Find all streams that have a group with the specified name
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
        response.append({
            "id": s.id,
            "event_name": s.event_name,
            "stream_type": s.stream_type,
            "is_ignored": s.is_ignored,
            "teacher": s.teacher.name if s.teacher else None,
            "groups": [{"name": g.group_name, "size": g.group_size} for g in s.groups]
        })
        
    return response

@router.patch("/streams/{stream_id}")
async def update_stream(stream_id: int, payload: StreamUpdateModel, db: AsyncSession = Depends(async_get_db)):
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
    
    import json
    response = []
    for t in teachers:
        blocked = []
        if t.restrictions_json:
            try:
                blocked = json.loads(t.restrictions_json)
            except:
                blocked = []
        
        response.append({
            "id": str(t.id),
            "name": t.name,
            "dept": "Кафедра", # Placeholder for now as it's not in the model
            "blocked": blocked
        })
    return response

@router.post("/teachers/{teacher_id}/restrictions")
async def update_teacher_restrictions(teacher_id: int, payload: TeacherRestrictionsModel, db: AsyncSession = Depends(async_get_db)):
    stmt = select(Teacher).where(Teacher.id == teacher_id)
    result = await db.execute(stmt)
    teacher = result.scalar_one_or_none()
    
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
        
    import json
    teacher.restrictions_json = json.dumps(payload.restrictions.dict())
    await db.commit()
    return {"detail": "Restrictions updated"}

@router.get("/stats")
async def get_scheduler_stats(db: AsyncSession = Depends(async_get_db)):
    # Total streams
    stmt_streams = select(func.count(Stream.id))
    result_streams = await db.execute(stmt_streams)
    total_streams = result_streams.scalar()
    
    # Ignored streams
    stmt_ignored = select(func.count(Stream.id)).where(Stream.is_ignored == True)
    result_ignored = await db.execute(stmt_ignored)
    ignored_streams = result_ignored.scalar()
    
    # Total groups
    stmt_groups = select(func.count(distinct(StreamGroup.group_name)))
    result_groups = await db.execute(stmt_groups)
    total_groups = result_groups.scalar()
    
    # Total teachers
    stmt_teachers = select(func.count(Teacher.id))
    result_teachers = await db.execute(stmt_teachers)
    total_teachers = result_teachers.scalar()
    
    return {
        "total_streams": total_streams,
        "active_streams": total_streams - ignored_streams,
        "ignored_streams": ignored_streams,
        "total_groups": total_groups,
        "total_teachers": total_teachers
    }

@router.post("/generate")
async def start_generation(payload: GenerationTaskModel, db: AsyncSession = Depends(async_get_db)):
    # For now, just log and return 200
    print(f"Received generation task for groups: {payload.groups}")
    print(f"Holidays: {payload.holidays}")
    return {"status": "ok", "message": "Task received", "task_id": "gen_12345"}
