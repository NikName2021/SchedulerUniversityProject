from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SubjectRuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lectures: int = Field(default=1, ge=0, le=14)
    seminars: int = Field(default=1, ge=0, le=14)
    laboratories: int = Field(default=0, ge=0, le=14)
    days_per_week: int = Field(default=2, ge=1, le=6)
    weekdays: list[int] = Field(default_factory=list, max_length=6)
    days_hard: bool = False
    lecture_before_practice: bool = True
    time_preference: Literal["morning", "day", "evening"] = "day"

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, values: list[int]) -> list[int]:
        if any(value not in range(6) for value in values):
            raise ValueError("Выберите дни с понедельника по субботу")
        return sorted(set(values))

    @model_validator(mode="after")
    def valid_composition(self) -> "SubjectRuleConfig":
        total = self.lectures + self.seminars + self.laboratories
        if total == 0:
            raise ValueError("Добавьте хотя бы одно занятие")
        if self.days_per_week > total:
            raise ValueError("Число учебных дней не может превышать число пар")
        if self.days_hard and self.weekdays and len(self.weekdays) < self.days_per_week:
            raise ValueError("Выбранных дней меньше, чем учебных дней в неделю")
        return self


class SubjectRuleContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groups: list[str] = Field(min_length=1, max_length=1000)
    start_date: date
    end_date: date
    week_ids: list[int] = Field(default_factory=list, max_length=60)
    enabled_types: list[str] = Field(default_factory=list, max_length=20)
    holidays: list[date] = Field(default_factory=list, max_length=366)

    @field_validator("groups")
    @classmethod
    def valid_groups(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 255 for value in values):
            raise ValueError("Некорректные названия групп")
        return sorted({value.strip() for value in values})

    @model_validator(mode="after")
    def valid_dates(self) -> "SubjectRuleContext":
        if not 0 <= (self.end_date - self.start_date).days <= 366:
            raise ValueError("Период должен составлять от 1 до 367 дней")
        self.week_ids = sorted(set(self.week_ids))
        if not self.week_ids and (self.end_date - self.start_date).days > 6:
            raise ValueError("Для нескольких недель выберите учебный период")
        return self


class SubjectRuleWrite(SubjectRuleContext):
    subject: str = Field(min_length=1, max_length=500)
    rule: SubjectRuleConfig
