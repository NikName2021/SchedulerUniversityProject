"""
Schedule Quality Analysis Service.

Analyzes a group's schedule and returns a quality score (0-100)
with detailed breakdown by 6 criteria.
"""

import logging
import math
from collections import defaultdict
from typing import Any

from database.all_models import ScheduleEntry
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

# Weight allocation for each criterion (must sum to 100)
WEIGHT_WINDOWS = 25
WEIGHT_LATE = 15
WEIGHT_BALANCE = 20
WEIGHT_LUNCH = 10
WEIGHT_PROGRESS = 15
WEIGHT_AVAILABILITY = 15

PENALTY_PER_WINDOW = 5  # points lost per window gap
PENALTY_PER_LUNCH = 5  # points lost per lunch violation
PENALTY_PER_PROGRESS = 5  # points lost per progress violation
PENALTY_PER_WARNING = 3  # points lost per teacher warning


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _analyze_windows(
    days_data: dict[str, list[int]],
) -> dict[str, Any]:
    """Criterion 1: Gaps between lessons in a day."""
    total_windows = 0
    issues: list[str] = []

    for date_str, lessons in days_data.items():
        if len(lessons) < 2:
            continue
        sorted_l = sorted(lessons)
        first, last = sorted_l[0], sorted_l[-1]
        span = last - first + 1
        actual = len(sorted_l)

        # Subtract 1 if both 3rd and 4th slots are occupied (lunch break)
        has_lunch_overlap = 3 in sorted_l and 4 in sorted_l
        gaps = span - actual - (1 if has_lunch_overlap else 0)

        if gaps > 0:
            total_windows += gaps
            issues.append(f"{date_str}: {gaps} окно(а) в расписании")

    deduction = total_windows * PENALTY_PER_WINDOW
    score = max(0, WEIGHT_WINDOWS - deduction)
    return {
        "score": score,
        "max": WEIGHT_WINDOWS,
        "total_windows": total_windows,
        "issues": issues,
    }


def _analyze_late_lessons(all_lessons: list[int]) -> dict[str, Any]:
    """Criterion 2: Average lesson number (earlier = better)."""
    if not all_lessons:
        return {"score": WEIGHT_LATE, "max": WEIGHT_LATE, "avg_pair": 0}

    avg = sum(all_lessons) / len(all_lessons)
    # avg=1 → 100%, avg=2.5 → 100%, avg=4 → ~53%, avg=6 → 0%
    ratio = _clamp(1.0 - (avg - 2.5) / 3.5, 0.0, 1.0)
    score = round(WEIGHT_LATE * ratio)
    return {
        "score": score,
        "max": WEIGHT_LATE,
        "avg_pair": round(avg, 1),
    }


def _analyze_balance(days_data: dict[str, list[int]]) -> dict[str, Any]:
    """Criterion 3: Evenness of daily lesson count."""
    if not days_data:
        return {
            "score": WEIGHT_BALANCE,
            "max": WEIGHT_BALANCE,
            "std_dev": 0,
            "per_day": [],
        }

    counts = [len(v) for v in days_data.values()]
    if len(counts) <= 1:
        return {
            "score": WEIGHT_BALANCE,
            "max": WEIGHT_BALANCE,
            "std_dev": 0,
            "per_day": counts,
        }

    mean = sum(counts) / len(counts)
    variance = sum((c - mean) ** 2 for c in counts) / len(counts)
    std = math.sqrt(variance)

    # std=0 → 100%, std>=3 → 0%
    ratio = _clamp(1.0 - std / 3.0, 0.0, 1.0)
    score = round(WEIGHT_BALANCE * ratio)
    return {
        "score": score,
        "max": WEIGHT_BALANCE,
        "std_dev": round(std, 2),
        "per_day": counts,
    }


def _analyze_lunch(days_data: dict[str, list[int]]) -> dict[str, Any]:
    """Criterion 4: Days where both 3rd and 4th slots are occupied."""
    violations = 0
    violation_dates: list[str] = []

    for date_str, lessons in days_data.items():
        if 3 in lessons and 4 in lessons:
            violations += 1
            violation_dates.append(date_str)

    deduction = violations * PENALTY_PER_LUNCH
    score = max(0, WEIGHT_LUNCH - deduction)
    return {
        "score": score,
        "max": WEIGHT_LUNCH,
        "violations": violations,
        "violation_dates": violation_dates,
    }


def _analyze_progress(
    entries: list[ScheduleEntry],
) -> dict[str, Any]:
    """Criterion 5: Seminars should not precede lectures for the same subject."""
    # Group by event_name → {type → [dates]}
    subject_dates: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for e in entries:
        if not e.date:
            continue
        date_str = e.date.strftime("%Y-%m-%d") if hasattr(e.date, "strftime") else str(e.date)
        stype = (e.stream_type or "").lower()

        if "лекция" in stype or "lecture" in stype:
            subject_dates[e.event_name]["lecture"].append(date_str)
        elif "семинар" in stype or "practice" in stype:
            subject_dates[e.event_name]["seminar"].append(date_str)

    violations = 0
    issues: list[str] = []

    for subj, types in subject_dates.items():
        lectures = sorted(types.get("lecture", []))
        seminars = sorted(types.get("seminar", []))
        if not lectures or not seminars:
            continue
        first_lecture = lectures[0]
        for sem_date in seminars:
            if sem_date < first_lecture:
                violations += 1
                issues.append(
                    f"{subj}: семинар {sem_date} до первой лекции {first_lecture}"
                )

    deduction = violations * PENALTY_PER_PROGRESS
    score = max(0, WEIGHT_PROGRESS - deduction)
    return {
        "score": score,
        "max": WEIGHT_PROGRESS,
        "violations": violations,
        "issues": issues,
    }


def _analyze_availability(entries: list[ScheduleEntry]) -> dict[str, Any]:
    """Criterion 6: Entries with teacher availability warnings."""
    warning_count = 0
    warnings: list[str] = []

    for e in entries:
        if e.warning:
            warning_count += 1
            date_str = (
                e.date.strftime("%Y-%m-%d")
                if e.date and hasattr(e.date, "strftime")
                else "?"
            )
            warnings.append(f"{e.event_name} ({date_str}): {e.warning}")

    deduction = warning_count * PENALTY_PER_WARNING
    score = max(0, WEIGHT_AVAILABILITY - deduction)
    return {
        "score": score,
        "max": WEIGHT_AVAILABILITY,
        "warning_count": warning_count,
        "warnings": warnings,
    }


def _build_recommendations(details: dict[str, Any]) -> list[str]:
    """Generate human-readable recommendations based on analysis results."""
    recs: list[str] = []

    if details["windows"]["total_windows"] > 0:
        recs.append(
            f'Сократите {details["windows"]["total_windows"]} окно(а) — '
            "перенесите пары ближе друг к другу"
        )

    if details["late_lessons"]["avg_pair"] > 4.0:
        recs.append(
            f'Средняя пара = {details["late_lessons"]["avg_pair"]}. '
            "Перенесите занятия на более ранние слоты"
        )

    if details["balance"]["std_dev"] > 1.5:
        recs.append(
            "Нагрузка по дням неравномерная — распределите пары равномернее"
        )

    if details["lunch"]["violations"] > 0:
        recs.append(
            f'В {details["lunch"]["violations"]} дн. занята 3-я и 4-я пара. '
            "Освободите слот под обед"
        )

    for issue in details["progress"].get("issues", [])[:3]:
        recs.append(f"Нарушение порядка: {issue}")

    if details["availability"]["warning_count"] > 0:
        recs.append(
            f'{details["availability"]["warning_count"]} конфликт(ов) '
            "с доступностью педагогов — проверьте предупреждения"
        )

    return recs


class ScheduleQualityService:
    """Analyzes schedule quality for a specific group."""

    @staticmethod
    async def analyze(
        task_id: int, group_name: str, db: AsyncSession
    ) -> dict[str, Any]:
        stmt = (
            select(ScheduleEntry)
            .options(selectinload(ScheduleEntry.teacher))
            .where(
                ScheduleEntry.task_id == task_id,
                ScheduleEntry.group_name == group_name,
            )
        )
        result = await db.execute(stmt)
        entries = list(result.scalars().all())

        assigned = [e for e in entries if e.date and e.lesson_number]

        if not assigned:
            return {
                "score": 0,
                "grade": "F",
                "total_entries": len(entries),
                "assigned_entries": 0,
                "details": {},
                "recommendations": ["Нет выставленных пар для анализа"],
            }

        # Build per-day data: {date_str -> [lesson_numbers]}
        days_data: dict[str, list[int]] = defaultdict(list)
        all_lessons: list[int] = []
        for e in assigned:
            date_str = (
                e.date.strftime("%Y-%m-%d")
                if hasattr(e.date, "strftime")
                else str(e.date)
            )
            days_data[date_str].append(e.lesson_number)
            all_lessons.append(e.lesson_number)

        # Run all 6 analyses
        details = {
            "windows": _analyze_windows(days_data),
            "late_lessons": _analyze_late_lessons(all_lessons),
            "balance": _analyze_balance(days_data),
            "lunch": _analyze_lunch(days_data),
            "progress": _analyze_progress(assigned),
            "availability": _analyze_availability(assigned),
        }

        total_score = sum(d["score"] for d in details.values())
        total_score = int(_clamp(total_score, 0, 100))

        recommendations = _build_recommendations(details)

        return {
            "score": total_score,
            "grade": _grade(total_score),
            "total_entries": len(entries),
            "assigned_entries": len(assigned),
            "details": details,
            "recommendations": recommendations,
        }
