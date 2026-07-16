import datetime
import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
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
    file_path = Column(String, nullable=True)
    file_type = Column(Enum(FileType), nullable=False)
    created_date = Column(DateTime, default=datetime.datetime.now)
    status = Column(String, default="completed")  # processing, completed, error
    error_message = Column(String, nullable=True)

    streams = relationship(
        "Stream", cascade="all,delete", back_populates="import_batch"
    )


class Teacher(DeclBase):
    __tablename__ = "teacher"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    restrictions_json = Column(String, nullable=True)  # JSON string representation

    streams = relationship("Stream", back_populates="teacher")


class Stream(DeclBase):
    __tablename__ = "stream"
    id = Column(Integer, primary_key=True, autoincrement=True)
    import_batch_id = Column(
        Integer, ForeignKey("import_batch.id", ondelete="CASCADE"), nullable=False
    )
    teacher_id = Column(Integer, ForeignKey("teacher.id"), nullable=True)

    event_name = Column(String, nullable=False)
    stream_type = Column(String, nullable=True)
    lessons_count = Column(Integer, default=1)
    is_ignored = Column(Boolean, default=False)

    import_batch = relationship("ImportBatch", back_populates="streams")
    teacher = relationship("Teacher", back_populates="streams")
    groups = relationship("StreamGroup", cascade="all,delete", back_populates="stream")


class StreamGroup(DeclBase):
    __tablename__ = "stream_group"
    __table_args__ = (Index("ix_stream_group_group_name", "group_name"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    stream_id = Column(
        Integer, ForeignKey("stream.id", ondelete="CASCADE"), nullable=False
    )
    student_group_id = Column(
        Integer, ForeignKey("student_group.id", ondelete="SET NULL"), nullable=True
    )
    group_name = Column(String, nullable=False)
    group_size = Column(Integer, nullable=False)

    stream = relationship("Stream", back_populates="groups")
    student_group = relationship("StudentGroup", back_populates="stream_links")


class StudentGroup(DeclBase):
    __tablename__ = "student_group"
    __table_args__ = (
        CheckConstraint("student_count >= 0", name="ck_student_group_size"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    specialty = Column(String, nullable=True)
    course = Column(Integer, nullable=True)
    education_form = Column(String, nullable=True)
    student_count = Column(Integer, nullable=False, default=0)
    min_weekly_lessons = Column(Integer, nullable=True)
    max_weekly_lessons = Column(Integer, nullable=True)

    stream_links = relationship("StreamGroup", back_populates="student_group")


class AcademicPeriod(DeclBase):
    __tablename__ = "academic_period"
    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="ck_academic_period_dates"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    period_type = Column(String, nullable=False, default="semester")
    education_level = Column(String, nullable=True)
    starts_on = Column(Date, nullable=False)
    ends_on = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="draft")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    weeks = relationship(
        "PlanningWeek",
        cascade="all,delete-orphan",
        back_populates="period",
        order_by="PlanningWeek.sequence_number",
    )


class PlanningWeek(DeclBase):
    __tablename__ = "planning_week"
    __table_args__ = (
        UniqueConstraint("period_id", "sequence_number"),
        UniqueConstraint("period_id", "starts_on"),
        CheckConstraint("ends_on >= starts_on", name="ck_planning_week_dates"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    period_id = Column(
        Integer, ForeignKey("academic_period.id", ondelete="CASCADE"), nullable=False
    )
    sequence_number = Column(Integer, nullable=False)
    starts_on = Column(Date, nullable=False)
    ends_on = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="draft")

    period = relationship("AcademicPeriod", back_populates="weeks")
    demands = relationship(
        "WeeklyLessonDemand", cascade="all,delete-orphan", back_populates="week"
    )
    generation_tasks = relationship("GenerationTask", back_populates="planning_week")


class WeeklyLessonDemand(DeclBase):
    __tablename__ = "weekly_lesson_demand"
    __table_args__ = (
        UniqueConstraint("week_id", "stream_id"),
        CheckConstraint("lessons_count >= 0", name="ck_weekly_lesson_demand_count"),
        CheckConstraint(
            "priority >= 1 AND priority <= 10",
            name="ck_weekly_lesson_demand_priority",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    week_id = Column(
        Integer, ForeignKey("planning_week.id", ondelete="CASCADE"), nullable=False
    )
    stream_id = Column(
        Integer, ForeignKey("stream.id", ondelete="CASCADE"), nullable=False
    )
    lessons_count = Column(Integer, nullable=False)
    priority = Column(Integer, nullable=False, default=5)

    week = relationship("PlanningWeek", back_populates="demands")
    stream = relationship("Stream")


class GenerationTask(DeclBase):
    __tablename__ = "generation_task"
    __table_args__ = (Index("ix_generation_task_planning_week_id", "planning_week_id"),)
    id = Column(Integer, primary_key=True, index=True)
    planning_week_id = Column(
        Integer, ForeignKey("planning_week.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default="pending")  # pending, success, failed
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    groups_json = Column(String)  # List of groups
    holidays_json = Column(String)  # List of holidays
    settings_json = Column(String)  # Dict of other settings
    result_count = Column(Integer, default=0)
    error_message = Column(String, nullable=True)
    total_components = Column(Integer, nullable=False, default=0)
    completed_components = Column(Integer, nullable=False, default=0)
    progress_percent = Column(Integer, nullable=False, default=0)
    metrics_json = Column(String, nullable=True)
    celery_workflow_id = Column(String, nullable=True)

    planning_week = relationship("PlanningWeek", back_populates="generation_tasks")
    components = relationship(
        "GenerationComponent", cascade="all,delete-orphan", back_populates="task"
    )


class GenerationComponent(DeclBase):
    __tablename__ = "generation_component"
    __table_args__ = (
        UniqueConstraint("task_id", "component_key"),
        Index("ix_generation_component_task_status", "task_id", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(
        Integer, ForeignKey("generation_task.id", ondelete="CASCADE"), nullable=False
    )
    component_key = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    event_count = Column(Integer, nullable=False, default=0)
    variable_count = Column(Integer, nullable=False, default=0)
    constraint_count = Column(Integer, nullable=False, default=0)
    solve_seconds = Column(Float, nullable=True)
    objective = Column(Float, nullable=True)
    error_message = Column(String, nullable=True)

    task = relationship("GenerationTask", back_populates="components")


class ScheduleEntry(DeclBase):
    __tablename__ = "schedule_entry"
    __table_args__ = (
        Index(
            "ix_schedule_entry_teacher_slot",
            "teacher_id",
            "date",
            "lesson_number",
        ),
        Index("ix_schedule_entry_room_slot", "room_id", "date", "lesson_number"),
        Index(
            "ix_schedule_entry_group_slot",
            "group_name",
            "date",
            "lesson_number",
        ),
    )
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("generation_task.id"), nullable=True)
    planning_week_id = Column(
        Integer, ForeignKey("planning_week.id", ondelete="SET NULL"), nullable=True
    )
    source_stream_id = Column(
        Integer, ForeignKey("stream.id", ondelete="SET NULL"), nullable=True
    )
    group_name = Column(String, nullable=False)
    event_name = Column(String, nullable=False)
    stream_type = Column(String, nullable=False)
    teacher_id = Column(Integer, ForeignKey("teacher.id"), nullable=True)
    room_id = Column(String, nullable=True)
    date = Column(DateTime, nullable=True)
    lesson_number = Column(Integer, nullable=True)
    warning = Column(String, nullable=True)
    is_locked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

    teacher = relationship("Teacher")


async def create_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(DeclBase.metadata.create_all)
