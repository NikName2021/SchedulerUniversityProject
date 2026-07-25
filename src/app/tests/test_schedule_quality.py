import datetime

from database import ScheduleEntry
from services.quality_service import _analyze_progress


def test_progress_detects_seminar_before_lecture_on_same_day() -> None:
    entries = [
        ScheduleEntry(
            group_name="ГР-1",
            event_name="Математика",
            stream_type="Семинар",
            date=datetime.datetime(2026, 9, 7),
            lesson_number=1,
        ),
        ScheduleEntry(
            group_name="ГР-1",
            event_name="Математика",
            stream_type="Лекция",
            date=datetime.datetime(2026, 9, 7),
            lesson_number=2,
        ),
    ]

    result = _analyze_progress(entries)

    assert result["violations"] == 1
    assert result["score"] < result["max"]
