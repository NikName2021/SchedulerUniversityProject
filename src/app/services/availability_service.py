import datetime
import json
import re
from collections import defaultdict
from typing import Any

from core.constants import ALL_LESSONS, STUDY_DAYS
from database import AvailabilityRule, Teacher
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


def _legacy_teacher_unavailable(
    raw_restrictions: str, dates: list[datetime.date]
) -> list[list[Any]]:
    try:
        restrictions = json.loads(raw_restrictions)
    except (TypeError, json.JSONDecodeError):
        return []
    if isinstance(restrictions, list):
        restrictions = {"recurring": restrictions}
    if not isinstance(restrictions, dict):
        return []

    recurring: set[tuple[int, int]] = set()
    for value in restrictions.get("recurring") or []:
        match = re.fullmatch(r"([0-6])[-_:]([1-7])", str(value))
        if match:
            recurring.add(((int(match[1]) - 1) % 7, int(match[2])))
    specific: set[tuple[str, int]] = set()
    for value in restrictions.get("specific") or []:
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[-_:]([1-7])", str(value))
        if match:
            specific.add((match[1], int(match[2])))

    whitelist = restrictions.get("mode") == "whitelist"
    result = []
    for day in dates:
        date_key = day.isoformat()
        for lesson in ALL_LESSONS:
            marked = (day.weekday(), lesson) in recurring or (
                date_key,
                lesson,
            ) in specific
            if marked != whitelist:
                result.append([date_key, lesson])
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

    structured_teacher_ids = {rule.teacher_id for rule in rules if rule.teacher_id}
    legacy_teachers = await db.execute(
        select(Teacher.name, Teacher.restrictions_json).where(
            Teacher.restrictions_json.is_not(None),
            Teacher.id.not_in(structured_teacher_ids),
        )
    )
    for teacher_name, restrictions in legacy_teachers:
        blocked = _legacy_teacher_unavailable(restrictions, dates)
        if blocked:
            unavailable["teacher"][teacher_name].extend(blocked)

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
    }
