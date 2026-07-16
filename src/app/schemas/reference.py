from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DepartmentCreate(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=255)


class DepartmentRead(DepartmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class BuildingCreate(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=500)


class BuildingRead(BuildingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RoomFeatureCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)


class RoomFeatureRead(RoomFeatureCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ActivityTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    room_type: str | None = Field(default=None, max_length=50)
    is_shared_for_groups: bool = False
    color: str | None = Field(default=None, max_length=20)
    is_active: bool = True


class ActivityTypeRead(ActivityTypeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class DisciplineCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=500)
    short_name: str | None = Field(default=None, max_length=100)
    external_id: str | None = Field(default=None, max_length=100)


class DisciplineRead(DisciplineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RoomCreate(BaseModel):
    building_id: int | None = None
    owner_department_id: int | None = None
    code: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=255)
    floor: int | None = None
    capacity: int = Field(ge=0)
    room_type: str = Field(default="mixed", min_length=1, max_length=50)
    is_active: bool = True
    feature_ids: list[int] = Field(default_factory=list)


class RoomUpdate(BaseModel):
    building_id: int | None = None
    owner_department_id: int | None = None
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=255)
    floor: int | None = None
    capacity: int | None = Field(default=None, ge=0)
    room_type: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None
    feature_ids: list[int] | None = None


class RoomRead(BaseModel):
    id: int
    building_id: int | None
    building_name: str | None
    owner_department_id: int | None
    code: str
    name: str | None
    floor: int | None
    capacity: int
    room_type: str
    is_active: bool
    features: list[RoomFeatureRead]


class AvailabilityRuleCreate(BaseModel):
    teacher_id: int | None = None
    student_group_id: int | None = None
    room_id: int | None = None
    is_global: bool = False
    rule_kind: str = Field(pattern="^(unavailable|available|preferred)$")
    recurrence: str = Field(pattern="^(weekly|specific|date_range)$")
    weekday: int | None = Field(default=None, ge=0, le=6)
    specific_date: date | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    lesson_start: int = Field(ge=1, le=20)
    lesson_end: int = Field(ge=1, le=20)
    is_hard: bool = True
    weight: int = Field(default=5, ge=1, le=10)
    description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_rule(self) -> "AvailabilityRuleCreate":
        scopes = sum(
            value is not None
            for value in (self.teacher_id, self.student_group_id, self.room_id)
        ) + int(self.is_global)
        if scopes != 1:
            raise ValueError("Exactly one resource scope is required")
        if self.lesson_end < self.lesson_start:
            raise ValueError("lesson_end must not precede lesson_start")
        if self.recurrence == "weekly" and self.weekday is None:
            raise ValueError("weekday is required for weekly recurrence")
        if self.recurrence == "specific" and self.specific_date is None:
            raise ValueError("specific_date is required for specific recurrence")
        if self.recurrence == "date_range":
            if self.starts_on is None or self.ends_on is None:
                raise ValueError("starts_on and ends_on are required for date_range")
            if self.ends_on < self.starts_on:
                raise ValueError("ends_on must not precede starts_on")
        return self


class AvailabilityRuleRead(AvailabilityRuleCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class RuleSettingInput(BaseModel):
    rule_code: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    is_hard: bool = False
    weight: int = Field(default=5, ge=1, le=10)


class RuleSettingRead(RuleSettingInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    profile_id: int


class RuleProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    education_level: str | None = Field(default=None, max_length=100)
    is_default: bool = False
    is_active: bool = True
    settings: list[RuleSettingInput] = Field(default_factory=list)


class RuleProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    education_level: str | None
    is_default: bool
    is_active: bool
    settings: list[RuleSettingRead]


class RuleSettingsUpdate(BaseModel):
    settings: list[RuleSettingInput]


class TeacherProfileUpdate(BaseModel):
    department_id: int | None = None
    position: str | None = Field(default=None, max_length=255)


class TeacherProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    department_id: int | None
    position: str | None


class StudentGroupProfileUpdate(BaseModel):
    specialty: str | None = Field(default=None, max_length=255)
    course: int | None = Field(default=None, ge=1, le=10)
    education_form: str | None = Field(default=None, max_length=100)
    student_count: int | None = Field(default=None, ge=0)
    min_weekly_lessons: int | None = Field(default=None, ge=0)
    max_weekly_lessons: int | None = Field(default=None, ge=0)


class StudentGroupProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    specialty: str | None
    course: int | None
    education_form: str | None
    student_count: int
    min_weekly_lessons: int | None
    max_weekly_lessons: int | None


class StreamRequirementsUpdate(BaseModel):
    discipline_id: int | None = None
    activity_type_id: int | None = None
    required_room_id: int | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    feature_ids: list[int] | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "StreamRequirementsUpdate":
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("ends_on must not precede starts_on")
        return self


class StreamRequirementsRead(BaseModel):
    id: int
    discipline_id: int | None
    activity_type_id: int | None
    required_room_id: int | None
    starts_on: date | None
    ends_on: date | None
    feature_ids: list[int]
