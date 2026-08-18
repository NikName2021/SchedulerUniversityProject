import datetime
from collections import defaultdict
from typing import Any

from core.constants import ALL_LESSONS, STUDY_DAYS
from database import AvailabilityRule
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


def _period_dates(start_date: str, end_date: str) -> list[datetime.date]:
    current = datetime.date.fromisoformat(start_date)
    last_date = datetime.date.fromisoformat(end_date)
    dates = []
    while current <= last_date:
        if current.weekday() in STUDY_DAYS:
            dates.append(current)
        current += datetime.timedelta(days=1)
    return dates


def _rule_slots(rule: AvailabilityRule, dates: list[datetime.date]) -> list[list[Any]]:
    result: list[list[Any]] = []
    for current in dates:
        applies = False
        if rule.recurrence == "weekly":
            applies = current.weekday() == rule.weekday
            if rule.starts_on and current < rule.starts_on:
                applies = False
            if rule.ends_on and current > rule.ends_on:
                applies = False
        elif rule.recurrence == "specific":
            applies = current == rule.specific_date
        elif rule.recurrence == "date_range":
            applies = bool(
                rule.starts_on
                and rule.ends_on
                and rule.starts_on <= current <= rule.ends_on
                and (rule.weekday is None or current.weekday() == rule.weekday)
            )
        if applies:
            result.extend(
                [current.isoformat(), lesson]
                for lesson in range(rule.lesson_start, rule.lesson_end + 1)
            )
    return result


async def build_availability_context(
    db: AsyncSession, start_date: str, end_date: str
) -> dict[str, Any]:
    result = await db.execute(
        select(AvailabilityRule).options(
            selectinload(AvailabilityRule.teacher),
            selectinload(AvailabilityRule.student_group),
            selectinload(AvailabilityRule.room),
        )
    )
    rules = list(result.scalars())
    dates = _period_dates(start_date, end_date)
    all_slots = {
        (current.isoformat(), lesson) for current in dates for lesson in ALL_LESSONS
    }

    unavailable: dict[str, dict[str, list[list[Any]]]] = {
        "teacher": defaultdict(list),
        "group": defaultdict(list),
        "room": defaultdict(list),
        "global": defaultdict(list),
    }
    preferred: dict[str, dict[str, list[dict[str, Any]]]] = {
        "teacher": defaultdict(list),
        "group": defaultdict(list),
    }
    discouraged: dict[str, dict[str, list[dict[str, Any]]]] = {
        "teacher": defaultdict(list),
        "group": defaultdict(list),
    }
    available_rules: dict[tuple[str, str], set[tuple[str, int]]] = defaultdict(set)

    for rule in rules:
        if rule.teacher:
            category, resource = "teacher", rule.teacher.name
        elif rule.student_group:
            category, resource = "group", rule.student_group.name
        elif rule.room:
            category, resource = "room", rule.room.code
        else:
            category, resource = "global", "*"
        slots = _rule_slots(rule, dates)
        if rule.rule_kind == "available" and rule.is_hard:
            available_rules[(category, resource)].update(
                (str(day), int(lesson)) for day, lesson in slots
            )
        elif rule.rule_kind == "unavailable" and rule.is_hard:
            unavailable[category][resource].extend(slots)
        elif rule.rule_kind == "preferred":
            if category in preferred:
                preferred[category][resource].append(
                    {"slots": slots, "weight": rule.weight}
                )
        elif rule.rule_kind == "unavailable":
            if category in discouraged:
                discouraged[category][resource].append(
                    {"slots": slots, "weight": rule.weight}
                )

    for (category, resource), allowed in available_rules.items():
        unavailable[category][resource].extend(
            [day, lesson] for day, lesson in sorted(all_slots - allowed)
        )

    return {
        "unavailable": {
            category: dict(resources) for category, resources in unavailable.items()
        },
        "preferred": {
            category: dict(resources) for category, resources in preferred.items()
        },
        "discouraged": {
            category: dict(resources) for category, resources in discouraged.items()
        },
        "structured_teacher_names": sorted(
            {rule.teacher.name for rule in rules if rule.teacher is not None}
        ),
    }
