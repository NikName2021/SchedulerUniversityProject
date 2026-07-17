from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AcademicPeriodCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    period_type: str = Field(default="semester", min_length=1, max_length=50)
    education_level: str | None = Field(default=None, max_length=100)
    starts_on: date
    ends_on: date
    create_weeks: bool = True

    @model_validator(mode="after")
    def validate_dates(self) -> "AcademicPeriodCreate":
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on must not be earlier than starts_on")
        return self


class PlanningWeekRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    period_id: int
    sequence_number: int
    starts_on: date
    ends_on: date
    status: str


class AcademicPeriodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    period_type: str
    education_level: str | None
    starts_on: date
    ends_on: date
    status: str
    created_at: datetime
    weeks: list[PlanningWeekRead] = Field(default_factory=list)


class WeeklyDemandItem(BaseModel):
    stream_id: int
    lessons_count: int = Field(ge=0)
    priority: int = Field(default=5, ge=1, le=10)


class WeeklyDemandBulkUpdate(BaseModel):
    demands: list[WeeklyDemandItem]


class WeeklyDemandRead(WeeklyDemandItem):
    model_config = ConfigDict(from_attributes=True)

    id: int
    week_id: int
    event_name: str | None = None
    stream_type: str | None = None
    teacher_name: str | None = None


class WeeklyDemandList(BaseModel):
    week_id: int
    demands: list[WeeklyDemandRead]


class WeeklyDemandCloneRequest(BaseModel):
    source_week_id: int | None = None
    use_stream_defaults: bool = False


class WeeklyDemandUpdateResult(BaseModel):
    week_id: int
    updated: int


class SemesterDemandDistributionRequest(BaseModel):
    groups: list[str] = Field(min_length=1)
    enabled_types: list[str] = Field(default_factory=list)
    holidays: list[date] = Field(default_factory=list)


class SemesterWeekDistribution(BaseModel):
    week_id: int
    sequence_number: int
    lessons_count: int
    streams_count: int


class SemesterDemandDistributionResult(BaseModel):
    period_id: int
    streams_count: int
    planned_lessons: int
    published_lessons: int
    distributed_lessons: int
    weeks: list[SemesterWeekDistribution]
