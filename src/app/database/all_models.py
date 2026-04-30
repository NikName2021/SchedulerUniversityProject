import datetime
import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger, Enum

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import declarative_base, relationship

DeclBase = declarative_base()

class FileType(enum.Enum):
    STREAMS = "streams"
    TEACHERS_LOAD = "teachers_load"
    ROOMS = "rooms"

class ImportBatch(DeclBase):
    __tablename__ = "import_batch"
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    file_type = Column(Enum(FileType), nullable=False)
    created_date = Column(DateTime, default=datetime.datetime.now)
    
    streams = relationship("Stream", cascade="all,delete", back_populates="import_batch")

class Teacher(DeclBase):
    __tablename__ = "teacher"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    restrictions_json = Column(String, nullable=True) # JSON string representation

    streams = relationship("Stream", back_populates="teacher")

class Stream(DeclBase):
    __tablename__ = "stream"
    id = Column(Integer, primary_key=True, autoincrement=True)
    import_batch_id = Column(Integer, ForeignKey("import_batch.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teacher.id"), nullable=True)
    
    event_name = Column(String, nullable=False)
    stream_type = Column(String, nullable=True)
    
    import_batch = relationship("ImportBatch", back_populates="streams")
    teacher = relationship("Teacher", back_populates="streams")
    groups = relationship("StreamGroup", cascade="all,delete", back_populates="stream")

class StreamGroup(DeclBase):
    __tablename__ = "stream_group"
    id = Column(Integer, primary_key=True, autoincrement=True)
    stream_id = Column(Integer, ForeignKey("stream.id", ondelete="CASCADE"), nullable=False)
    group_name = Column(String, nullable=False)
    group_size = Column(Integer, nullable=False)

    stream = relationship("Stream", back_populates="groups")

async def create_tables(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(DeclBase.metadata.create_all)
