import tempfile
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.config import async_get_db
from database.all_models import ImportBatch, FileType, Teacher, Stream, StreamGroup
from services.parser_service import parse_streams_content

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

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

    # Create ImportBatch
    batch = ImportBatch(filename=file.filename, file_type=FileType.STREAMS)
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
        
    await db.delete(batch)
    await db.commit()
    
    return {"detail": "Import batch and associated data deleted"}
