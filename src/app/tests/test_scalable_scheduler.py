import datetime

from services.scalable_scheduler import (
    assign_rooms_matching,
    build_conflict_components,
    solve_event_component,
)


def _context() -> dict:
    return {
        "start_date": "2026-09-07",
        "end_date": "2026-09-07",
        "immutable_before": "2026-09-07",
        "holidays": [],
        "study_days": [0],
        "lessons": [1, 2],
        "rooms": {
            "101": {"id": 1, "capacity": 30, "type": "sem", "features": []},
            "201": {"id": 2, "capacity": 120, "type": "lec", "features": []},
        },
        "unavailable": {"teacher": {}, "group": {}, "room": {}},
        "group_sizes": {},
        "max_time_seconds": 5,
        "num_workers": 1,
        "room_assignment_max_seconds": 2,
    }


def _event(
    event_id: str,
    groups: list[str],
    teacher_id: int | None,
    event_type: str = "sem",
) -> dict:
    return {
        "id": event_id,
        "stream_id": int(event_id.split("-")[-1]),
        "subject": event_id,
        "stream_type": "Лекция" if event_type == "lec" else "Семинар",
        "type": event_type,
        "teacher": f"Teacher {teacher_id}" if teacher_id else None,
        "teacher_id": teacher_id,
        "groups": groups,
        "lessons_count": 1,
        "priority": 5,
        "time_preference": "day",
    }


def test_conflict_graph_splits_independent_resources() -> None:
    events = [
        _event("event-1", ["A"], 1),
        _event("event-2", ["B"], 2),
        _event("event-3", ["C"], 1),
    ]

    components = build_conflict_components(events)

    assert sorted(len(component) for component in components) == [1, 2]
    assert {event["id"] for event in components[0]} == {"event-1", "event-3"}


def test_stream_lecture_uses_one_slot_variable_for_all_groups() -> None:
    event = _event(
        "event-1",
        [f"GROUP-{index}" for index in range(10)],
        1,
        event_type="lec",
    )

    result = solve_event_component([event], _context())

    assert result["status"] == "success"
    assert result["metrics"]["decision_variables"] == 2
    assert len(result["assignments"]) == 1
    assert len(result["assignments"][0]["groups"]) == 10


def test_shared_teacher_events_never_overlap() -> None:
    events = [
        _event("event-1", ["A"], 7),
        _event("event-2", ["B"], 7),
    ]

    result = solve_event_component(events, _context())

    assert result["status"] == "success"
    assert len(result["assignments"]) == 2
    assert len({tuple(item["slot"]) for item in result["assignments"]}) == 2


def test_three_stage_solver_reports_stage_metrics() -> None:
    context = _context()
    context["lessons"] = [1, 2, 3]
    events = [
        _event("event-1", ["A"], 1),
        _event("event-2", ["A"], 2),
    ]

    result = solve_event_component(events, context)

    assert result["status"] == "success"
    assert result["metrics"]["placement_objective"] == 0
    assert result["metrics"]["unassigned_count"] == 0
    assert result["metrics"]["stages"]["placement"]["status"] == "OPTIMAL"
    assert result["metrics"]["stages"]["windows"]["status"] == "OPTIMAL"
    assert result["metrics"]["stages"]["quality"]["status"] == "OPTIMAL"


def test_quality_stage_preserves_the_placement_result() -> None:
    events = [
        _event("event-1", ["A"], 1),
        _event("event-2", ["A"], 2),
        _event("event-3", ["A"], 3),
    ]

    result = solve_event_component(events, _context())

    assert result["status"] == "success"
    assert len(result["assignments"]) == 2
    assert sum(item["missing_count"] for item in result["unassigned"]) == 1
    assert result["metrics"]["placement_objective"] == 5
    assert result["metrics"]["unassigned_count"] == 1


def test_language_subgroups_can_run_in_parallel() -> None:
    context = _context()
    context["lessons"] = [1]
    first = _event("event-1", ["A (L1)"], 1)
    first["group_resources"] = ["A::L1"]
    second = _event("event-2", ["A (L2)"], 2)
    second["group_resources"] = ["A::L2"]

    result = solve_event_component([first, second], context)

    assert len(result["assignments"]) == 2
    assert {tuple(item["slot"]) for item in result["assignments"]} == {
        ("2026-09-07", 1)
    }


def test_full_group_conflicts_with_language_subgroup() -> None:
    context = _context()
    full_group = _event("event-1", ["A"], 1)
    full_group["group_resources"] = ["A::L1", "A::L2"]
    subgroup = _event("event-2", ["A (L1)"], 2)
    subgroup["group_resources"] = ["A::L1"]

    result = solve_event_component([full_group, subgroup], context)

    assert len(result["assignments"]) == 2
    assert len({tuple(item["slot"]) for item in result["assignments"]}) == 2


def test_heavily_loaded_group_gets_earlier_shared_teacher_slot() -> None:
    context = _context()
    context["lessons"] = [1, 6]
    context["group_lesson_loads"] = {"HEAVY": 24, "LIGHT": 3}
    events = [
        _event("event-1", ["HEAVY"], 7),
        _event("event-2", ["LIGHT"], 7),
    ]

    result = solve_event_component(events, context)

    lessons_by_group = {
        assignment["groups"][0]: assignment["slot"][1]
        for assignment in result["assignments"]
    }
    assert lessons_by_group == {"HEAVY": 1, "LIGHT": 6}


def test_room_matching_is_global_across_components() -> None:
    context = _context()
    context["rooms"] = {"101": {"capacity": 30, "type": "sem"}}
    context["group_sizes"] = {"A": 20, "B": 20}
    slot = [datetime.date(2026, 9, 7).isoformat(), 1]
    assignments = [
        {**_event("event-1", ["A"], 1), "slot": slot},
        {**_event("event-2", ["B"], 2), "slot": slot},
    ]

    completed, warnings, _metrics = assign_rooms_matching(assignments, context)

    assert sorted(item["room"] for item in completed) == ["101", "НЕТ АУДИТОРИИ"]
    assert len(warnings) == 1


def test_lunch_break_prevents_third_and_fourth_pair_together() -> None:
    context = _context()
    context["lessons"] = [3, 4]
    events = [
        _event("event-1", ["A"], 1),
        _event("event-2", ["A"], 2),
    ]

    result = solve_event_component(events, context)

    assert result["status"] == "success"
    assert len(result["assignments"]) == 1
    assert sum(item["missing_count"] for item in result["unassigned"]) == 1


def test_double_window_is_penalized() -> None:
    context = _context()
    context["lessons"] = [1, 2, 3, 4]
    first = _event("event-1", ["A"], 1)
    first["fixed_slot"] = ["2026-09-07", 1]
    second = _event("event-2", ["A"], 2)
    second["time_preference"] = "evening"

    result = solve_event_component([first, second], context)

    lessons_by_event = {
        assignment["id"]: assignment["slot"][1]
        for assignment in result["assignments"]
    }
    assert lessons_by_event == {"event-1": 1, "event-2": 2}
    assert result["metrics"]["window_objective"] == 0


def test_lecture_is_scheduled_before_practical() -> None:
    context = _context()
    lecture = _event("event-1", ["A"], 1, event_type="lec")
    lecture["subject"] = "Математика"
    practical = _event("event-2", ["A"], 2)
    practical["subject"] = "Математика"

    result = solve_event_component([lecture, practical], context)

    slots_by_type = {
        assignment["type"]: assignment["slot"][1]
        for assignment in result["assignments"]
    }
    assert slots_by_type["lec"] < slots_by_type["sem"]


def test_room_matching_honors_required_room_and_features() -> None:
    context = _context()
    context["rooms"] = {
        "101": {"id": 10, "capacity": 30, "type": "lab", "features": []},
        "LAB-1": {
            "id": 11,
            "capacity": 30,
            "type": "lab",
            "features": ["computers"],
        },
    }
    context["rule_settings"] = {
        "room_features": {"enabled": True, "is_hard": True, "weight": 10}
    }
    context["group_sizes"] = {"A": 20}
    event = _event("event-1", ["A"], 1, event_type="lab")
    event.update({"required_room": "LAB-1", "required_features": ["computers"]})

    completed, warnings, _metrics = assign_rooms_matching(
        [{**event, "slot": ["2026-09-07", 1]}], context
    )

    assert completed[0]["room"] == "LAB-1"
    assert completed[0]["room_ref_id"] == 11
    assert warnings == []


def test_global_unavailability_blocks_slot() -> None:
    context = _context()
    context["unavailable"]["global"] = {"*": [["2026-09-07", 1]]}

    result = solve_event_component([_event("event-1", ["A"], 1)], context)

    assert result["assignments"][0]["slot"] == ["2026-09-07", 2]
