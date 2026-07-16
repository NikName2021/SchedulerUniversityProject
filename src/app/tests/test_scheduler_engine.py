import datetime

from services.scheduler_engine import assign_rooms


def test_assign_rooms_keeps_laboratory_events() -> None:
    slot = (datetime.date(2026, 9, 7), 1)
    schedule = [
        {
            "group": "ИТ-101",
            "subject": "Программирование",
            "type": "lab",
            "slot": slot,
            "teacher": "Иванов И.И.",
            "teacher_id": 1,
        }
    ]

    result, warnings = assign_rooms(
        schedule=schedule,
        SLOTS=[slot],
        rooms={"Л-101": {"capacity": 25, "type": "lab"}},
        group_sizes={"ИТ-101": 20},
        subjects={},
        unavailable_times={},
    )

    assert len(result) == 1
    assert result[0]["room"] == "Л-101"
    assert warnings == []
