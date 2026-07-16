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


class Department(DeclBase):
    __tablename__ = "department"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=True, unique=True)
    name = Column(String, nullable=False, unique=True)


class ActivityType(DeclBase):
    __tablename__ = "activity_type"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False, unique=True)
    room_type = Column(String, nullable=True)
    is_shared_for_groups = Column(Boolean, nullable=False, default=False)
    color = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)


class Discipline(DeclBase):
    __tablename__ = "discipline"
    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String, nullable=False, unique=True)
    short_name = Column(String, nullable=True)
    external_id = Column(String, nullable=True, unique=True)


class Building(DeclBase):
    __tablename__ = "building"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=True, unique=True)
    name = Column(String, nullable=False, unique=True)
    address = Column(String, nullable=True)


class Room(DeclBase):
    __tablename__ = "room"
    __table_args__ = (
        UniqueConstraint("building_id", "code"),
        CheckConstraint("capacity >= 0", name="ck_room_capacity"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    building_id = Column(
        Integer, ForeignKey("building.id", ondelete="SET NULL"), nullable=True
    )
    owner_department_id = Column(
        Integer, ForeignKey("department.id", ondelete="SET NULL"), nullable=True
    )
    code = Column(String, nullable=False)
    name = Column(String, nullable=True)
    floor = Column(Integer, nullable=True)
    capacity = Column(Integer, nullable=False)
    room_type = Column(String, nullable=False, default="mixed")
    is_active = Column(Boolean, nullable=False, default=True)

    building = relationship("Building")
    owner_department = relationship("Department")
    feature_links = relationship(
        "RoomFeatureLink", cascade="all,delete-orphan", back_populates="room"
    )


class RoomFeature(DeclBase):
    __tablename__ = "room_feature"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False, unique=True)


class RoomFeatureLink(DeclBase):
    __tablename__ = "room_feature_link"
    __table_args__ = (UniqueConstraint("room_id", "feature_id"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey("room.id", ondelete="CASCADE"), nullable=False)
    feature_id = Column(
        Integer, ForeignKey("room_feature.id", ondelete="CASCADE"), nullable=False
    )

    room = relationship("Room", back_populates="feature_links")
    feature = relationship("RoomFeature")


class RuleProfile(DeclBase):
    __tablename__ = "rule_profile"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    education_level = Column(String, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    settings = relationship(
        "RuleSetting", cascade="all,delete-orphan", back_populates="profile"
    )


class RuleSetting(DeclBase):
    __tablename__ = "rule_setting"
    __table_args__ = (
        UniqueConstraint("profile_id", "rule_code"),
        CheckConstraint("weight >= 1 AND weight <= 10", name="ck_rule_weight"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(
        Integer, ForeignKey("rule_profile.id", ondelete="CASCADE"), nullable=False
    )
    rule_code = Column(String, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    is_hard = Column(Boolean, nullable=False, default=False)
    weight = Column(Integer, nullable=False, default=5)

    profile = relationship("RuleProfile", back_populates="settings")


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
    department_id = Column(
        Integer, ForeignKey("department.id", ondelete="SET NULL"), nullable=True
    )
    name = Column(String, nullable=False, unique=True)
    position = Column(String, nullable=True)
    restrictions_json = Column(String, nullable=True)  # JSON string representation

    streams = relationship("Stream", back_populates="teacher")
    department = relationship("Department")


class Stream(DeclBase):
    __tablename__ = "stream"
    id = Column(Integer, primary_key=True, autoincrement=True)
    import_batch_id = Column(
        Integer, ForeignKey("import_batch.id", ondelete="CASCADE"), nullable=False
    )
    teacher_id = Column(Integer, ForeignKey("teacher.id"), nullable=True)
    discipline_id = Column(
        Integer, ForeignKey("discipline.id", ondelete="SET NULL"), nullable=True
    )
    activity_type_id = Column(
        Integer, ForeignKey("activity_type.id", ondelete="SET NULL"), nullable=True
    )
    required_room_id = Column(
        Integer, ForeignKey("room.id", ondelete="SET NULL"), nullable=True
    )

    event_name = Column(String, nullable=False)
    stream_type = Column(String, nullable=True)
    lessons_count = Column(Integer, default=1)
    is_ignored = Column(Boolean, default=False)
    starts_on = Column(Date, nullable=True)
    ends_on = Column(Date, nullable=True)

    import_batch = relationship("ImportBatch", back_populates="streams")
    teacher = relationship("Teacher", back_populates="streams")
    discipline = relationship("Discipline")
    activity_type = relationship("ActivityType")
    required_room = relationship("Room")
    groups = relationship("StreamGroup", cascade="all,delete", back_populates="stream")
    feature_requirements = relationship(
        "StreamFeatureRequirement",
        cascade="all,delete-orphan",
        back_populates="stream",
    )


class StreamFeatureRequirement(DeclBase):
    __tablename__ = "stream_feature_requirement"
    __table_args__ = (UniqueConstraint("stream_id", "feature_id"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    stream_id = Column(
        Integer, ForeignKey("stream.id", ondelete="CASCADE"), nullable=False
    )
    feature_id = Column(
        Integer, ForeignKey("room_feature.id", ondelete="CASCADE"), nullable=False
    )
    is_hard = Column(Boolean, nullable=False, default=True)

    stream = relationship("Stream", back_populates="feature_requirements")
    feature = relationship("RoomFeature")


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


class AvailabilityRule(DeclBase):
    __tablename__ = "availability_rule"
    __table_args__ = (
        CheckConstraint(
            "teacher_id IS NOT NULL OR student_group_id IS NOT NULL OR room_id IS NOT NULL OR is_global = true",
            name="ck_availability_has_scope",
        ),
        CheckConstraint(
            "lesson_start >= 1 AND lesson_end >= lesson_start",
            name="ck_availability_lesson_range",
        ),
        CheckConstraint("weight >= 1 AND weight <= 10", name="ck_availability_weight"),
        Index("ix_availability_teacher", "teacher_id"),
        Index("ix_availability_group", "student_group_id"),
        Index("ix_availability_room", "room_id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    teacher_id = Column(
        Integer, ForeignKey("teacher.id", ondelete="CASCADE"), nullable=True
    )
    student_group_id = Column(
        Integer, ForeignKey("student_group.id", ondelete="CASCADE"), nullable=True
    )
    room_id = Column(Integer, ForeignKey("room.id", ondelete="CASCADE"), nullable=True)
    is_global = Column(Boolean, nullable=False, default=False)
    rule_kind = Column(String, nullable=False)  # unavailable, available, preferred
    recurrence = Column(String, nullable=False)  # weekly, specific, date_range
    weekday = Column(Integer, nullable=True)  # 0=Mon
    specific_date = Column(Date, nullable=True)
    starts_on = Column(Date, nullable=True)
    ends_on = Column(Date, nullable=True)
    lesson_start = Column(Integer, nullable=False)
    lesson_end = Column(Integer, nullable=False)
    is_hard = Column(Boolean, nullable=False, default=True)
    weight = Column(Integer, nullable=False, default=5)
    description = Column(String, nullable=True)

    teacher = relationship("Teacher")
    student_group = relationship("StudentGroup")
    room = relationship("Room")


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
    parent_task_id = Column(
        Integer, ForeignKey("generation_task.id", ondelete="SET NULL"), nullable=True
    )
    version_number = Column(Integer, nullable=False, default=1)
    publication_status = Column(String, nullable=False, default="draft")
    published_at = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    edit_revision = Column(Integer, nullable=False, default=0)
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
    celery_root_task_id = Column(String, nullable=True)
    celery_component_ids_json = Column(String, nullable=True)

    planning_week = relationship("PlanningWeek", back_populates="generation_tasks")
    components = relationship(
        "GenerationComponent", cascade="all,delete-orphan", back_populates="task"
    )
    locks = relationship(
        "GenerationLock", cascade="all,delete-orphan", back_populates="task"
    )
    issues = relationship(
        "GenerationIssue", cascade="all,delete-orphan", back_populates="task"
    )


class GenerationLock(DeclBase):
    __tablename__ = "generation_lock"
    scope_key = Column(String, primary_key=True)
    task_id = Column(
        Integer, ForeignKey("generation_task.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    task = relationship("GenerationTask", back_populates="locks")


class GenerationIssue(DeclBase):
    __tablename__ = "generation_issue"
    __table_args__ = (Index("ix_generation_issue_task_kind", "task_id", "kind"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(
        Integer, ForeignKey("generation_task.id", ondelete="CASCADE"), nullable=False
    )
    kind = Column(String, nullable=False)
    severity = Column(String, nullable=False, default="warning")
    message = Column(String, nullable=False)
    stream_id = Column(Integer, ForeignKey("stream.id", ondelete="SET NULL"))
    group_name = Column(String, nullable=True)
    date = Column(Date, nullable=True)
    lesson_number = Column(Integer, nullable=True)
    details_json = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    task = relationship("GenerationTask", back_populates="issues")


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
    room_ref_id = Column(
        Integer, ForeignKey("room.id", ondelete="SET NULL"), nullable=True
    )
    date = Column(DateTime, nullable=True)
    lesson_number = Column(Integer, nullable=True)
    warning = Column(String, nullable=True)
    is_locked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

    teacher = relationship("Teacher")
    room = relationship("Room")


async def create_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(DeclBase.metadata.create_all)
