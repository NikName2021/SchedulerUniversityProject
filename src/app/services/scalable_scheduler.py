from __future__ import annotations

import collections
import datetime
import time
from typing import Any

from core.config import (
    GROUP_LOAD_EARLY_PRIORITY_MULTIPLIER,
    GROUP_LOAD_EARLY_PRIORITY_STEP,
)
from core.constants import (
    NUM_WORKERS,
    PENALTY_LATE_LESSON,
    PENALTY_MORNING_PRIORITY,
    PENALTY_PROGRESS_VIOLATION,
    PENALTY_UNASSIGNED,
    PENALTY_WINDOW,
)
from ortools.sat.python import cp_model

Slot = tuple[datetime.date, int]


def _rule(
    context: dict[str, Any],
    code: str,
    *,
    enabled: bool = True,
    is_hard: bool = False,
    weight: int = 5,
) -> dict[str, Any]:
    configured = context.get("rule_settings", {}).get(code, {})
    return {
        "enabled": bool(configured.get("enabled", enabled)),
        "is_hard": bool(configured.get("is_hard", is_hard)),
        "weight": int(configured.get("weight", weight)),
    }


def build_conflict_components(
    events: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Split events by shared hard resources (groups and teachers)."""
    if not events:
        return []

    parent = list(range(len(events)))
    rank = [0] * len(events)

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if rank[left_root] < rank[right_root]:
            left_root, right_root = right_root, left_root
        parent[right_root] = left_root
        if rank[left_root] == rank[right_root]:
            rank[left_root] += 1

    resource_owner: dict[str, int] = {}
    for index, event in enumerate(events):
        resources = [
            f"group:{group}"
            for group in event.get("group_resources", event["groups"])
        ]
        if event.get("teacher_id") is not None:
            resources.append(f"teacher-id:{event['teacher_id']}")
        elif event.get("teacher"):
            resources.append(f"teacher-name:{event['teacher']}")

        for resource in resources:
            owner = resource_owner.setdefault(resource, index)
            union(index, owner)

    components: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    for index, event in enumerate(events):
        components[find(index)].append(event)

    result = list(components.values())
    result.sort(key=lambda component: (-len(component), component[0]["id"]))
    return result


def _generate_slots(context: dict[str, Any]) -> list[Slot]:
    start_date = datetime.date.fromisoformat(context["start_date"])
    end_date = datetime.date.fromisoformat(context["end_date"])
    immutable_before = datetime.date.fromisoformat(
        context.get("immutable_before", context["start_date"])
    )
    holidays = {datetime.date.fromisoformat(value) for value in context["holidays"]}
    study_days = set(context["study_days"])
    lessons = context["lessons"]

    slots: list[Slot] = []
    current = max(start_date, immutable_before)
    while current <= end_date:
        if current.weekday() in study_days and current not in holidays:
            slots.extend((current, lesson) for lesson in lessons)
        current += datetime.timedelta(days=1)
    return slots


def _normalize_unavailable(
    unavailable: dict[str, Any],
) -> dict[str, dict[str, set[tuple[Any, int]]]]:
    normalized: dict[str, dict[str, set[tuple[Any, int]]]] = {}
    for category, resources in unavailable.items():
        normalized[category] = {}
        for resource, raw_slots in resources.items():
            slots: set[tuple[Any, int]] = set()
            for raw_slot in raw_slots:
                day, lesson = raw_slot
                if isinstance(day, str) and len(day) == 10:
                    day = datetime.date.fromisoformat(day)
                slots.add((day, int(lesson)))
            normalized[category][str(resource)] = slots
    return normalized


def _event_slot_is_blocked(
    event: dict[str, Any],
    slot: Slot,
    unavailable: dict[str, dict[str, set[tuple[Any, int]]]],
) -> bool:
    date, lesson = slot
    recurring = (date.weekday(), lesson)
    specific = (date, lesson)

    global_slots = unavailable.get("global", {}).get("*", set())
    if recurring in global_slots or specific in global_slots:
        return True

    teacher_key = str(event.get("teacher") or "")
    teacher_slots = unavailable.get("teacher", {}).get(teacher_key, set())
    if recurring in teacher_slots or specific in teacher_slots:
        return True

    for group in event.get("base_groups", event["groups"]):
        group_slots = unavailable.get("group", {}).get(str(group), set())
        if recurring in group_slots or specific in group_slots:
            return True
    return False


def _preference_penalty(
    event: dict[str, Any],
    slot: Slot,
    rules: dict[str, dict[str, list[dict[str, Any]]]],
    *,
    preferred: bool,
) -> int:
    date_slot = [slot[0].isoformat(), slot[1]]
    recurring_slot = [slot[0].weekday(), slot[1]]
    resources = [("teacher", event.get("teacher"))]
    resources.extend(("group", group) for group in event["groups"])
    score = 0
    for category, resource in resources:
        if not resource:
            continue
        for rule in rules.get(category, {}).get(str(resource), []):
            if date_slot in rule["slots"] or recurring_slot in rule["slots"]:
                score += int(rule.get("weight", 5))
    return -score if preferred else score


def solve_event_component(
    events: list[dict[str, Any]], context: dict[str, Any]
) -> dict[str, Any]:
    """Solve one conflict-connected component without assigning rooms."""
    started_at = time.perf_counter()
    slots = _generate_slots(context)
    if not slots:
        return {
            "status": "failed",
            "assignments": [],
            "unassigned": [],
            "error": "No available slots in the selected period",
            "metrics": {"events": len(events), "variables": 0, "constraints": 0},
        }

    model = cp_model.CpModel()
    unavailable = _normalize_unavailable(context.get("unavailable", {}))
    by_day: dict[datetime.date, list[Slot]] = collections.defaultdict(list)
    for slot in slots:
        by_day[slot[0]].append(slot)

    variables: dict[tuple[str, Slot], cp_model.IntVar] = {}
    by_group_slot: dict[tuple[str, Slot], list[cp_model.IntVar]] = (
        collections.defaultdict(list)
    )
    by_teacher_slot: dict[tuple[str, Slot], list[cp_model.IntVar]] = (
        collections.defaultdict(list)
    )
    penalties: list[Any] = []
    deficits: dict[str, tuple[cp_model.IntVar, int]] = {}
    late_rule = _rule(context, "late_lessons", weight=5)
    preference_rule = _rule(context, "teacher_preferences", weight=5)
    group_lesson_loads = context.get("group_lesson_loads", {})

    for event in events:
        event_id = event["id"]
        event_variables: list[cp_model.IntVar] = []
        for slot in slots:
            if _event_slot_is_blocked(event, slot, unavailable):
                continue
            variable = model.NewBoolVar(
                f"event_{event_id}_{slot[0].isoformat()}_{slot[1]}"
            )
            variables[(event_id, slot)] = variable
            event_variables.append(variable)
            for resource in event.get("group_resources", event["groups"]):
                by_group_slot[(resource, slot)].append(variable)
            teacher_key = str(event.get("teacher_id") or event.get("teacher") or "")
            if teacher_key:
                by_teacher_slot[(teacher_key, slot)].append(variable)

            group_resources = event.get("group_resources", event["groups"])
            participant_weight = max(1, len(group_resources))
            if late_rule["enabled"]:
                event_group_load = max(
                    (
                        int(group_lesson_loads.get(group, 1))
                        for group in group_resources
                    ),
                    default=1,
                )
                load_priority = 1 + (
                    max(1, event_group_load) - 1
                ) // GROUP_LOAD_EARLY_PRIORITY_STEP
                penalties.append(
                    variable
                    * slot[1]
                    * PENALTY_LATE_LESSON
                    * participant_weight
                    * late_rule["weight"]
                    * load_priority
                    * GROUP_LOAD_EARLY_PRIORITY_MULTIPLIER
                )
            preference = event.get("time_preference", "day")
            if preference == "morning" and slot[1] > 2:
                penalties.append(variable * (slot[1] - 2) * PENALTY_MORNING_PRIORITY)
            elif preference == "evening" and slot[1] < 5:
                penalties.append(variable * (5 - slot[1]) * PENALTY_MORNING_PRIORITY)
            if preference_rule["enabled"]:
                preference_cost = _preference_penalty(
                    event, slot, context.get("discouraged", {}), preferred=False
                ) + _preference_penalty(
                    event, slot, context.get("preferred", {}), preferred=True
                )
                if preference_cost:
                    penalties.append(
                        variable * preference_cost * preference_rule["weight"]
                    )

        target = int(event["lessons_count"])
        deficit = model.NewIntVar(0, target, f"deficit_{event_id}")
        model.Add(sum(event_variables) + deficit == target)
        penalties.append(
            deficit
            * PENALTY_UNASSIGNED
            * max(1, len(event["groups"]))
            * max(1, int(event.get("priority", 5)))
        )
        deficits[event_id] = (deficit, target)

        for _day, day_slots in by_day.items():
            day_variables = [
                variables[(event_id, slot)]
                for slot in day_slots
                if (event_id, slot) in variables
            ]
            if day_variables:
                model.Add(sum(day_variables) <= 1)

        fixed_slot = event.get("fixed_slot")
        if fixed_slot:
            slot = (datetime.date.fromisoformat(fixed_slot[0]), int(fixed_slot[1]))
            variable = variables.get((event_id, slot))
            if variable is None:
                return {
                    "status": "failed",
                    "assignments": [],
                    "unassigned": [],
                    "error": f"Fixed slot is unavailable for event {event_id}",
                    "metrics": {
                        "events": len(events),
                        "variables": len(model.Proto().variables),
                        "constraints": len(model.Proto().constraints),
                    },
                }
            model.Add(variable == 1)

    for resource_variables in by_group_slot.values():
        if len(resource_variables) > 1:
            model.AddAtMostOne(resource_variables)
    for resource_variables in by_teacher_slot.values():
        if len(resource_variables) > 1:
            model.AddAtMostOne(resource_variables)

    progression_rule = _rule(context, "lecture_before_practice", weight=5)
    # Keep practical and laboratory progress behind lectures for the same group
    # and subject. These events already share a group and therefore always belong
    # to the same conflict component.
    for group in (
        sorted({group for event in events for group in event["groups"]})
        if progression_rule["enabled"]
        else []
    ):
        subjects = {event["subject"] for event in events if group in event["groups"]}
        for subject in subjects:
            lecture_events = [
                event
                for event in events
                if event["subject"] == subject
                and event["type"] == "lec"
                and group in event["groups"]
            ]
            practical_events = [
                event
                for event in events
                if event["subject"] == subject
                and event["type"] in {"sem", "lab"}
                and group in event["groups"]
            ]
            if not lecture_events or not practical_events:
                continue
            total_lectures = sum(
                int(event["lessons_count"]) for event in lecture_events
            )
            total_practicals = sum(
                int(event["lessons_count"]) for event in practical_events
            )
            cumulative_lectures: Any = 0
            cumulative_practicals: Any = 0
            for day in sorted(by_day):
                for slot in sorted(by_day[day], key=lambda value: value[1]):
                    cumulative_lectures += sum(
                        variables[(event["id"], slot)]
                        for event in lecture_events
                        if (event["id"], slot) in variables
                    )
                    cumulative_practicals += sum(
                        variables[(event["id"], slot)]
                        for event in practical_events
                        if (event["id"], slot) in variables
                    )
                    violation = model.NewIntVar(
                        -total_lectures * total_practicals,
                        total_lectures * total_practicals,
                        f"progress_{group}_{subject}_{day.isoformat()}_{slot[1]}",
                    )
                    model.Add(
                        violation
                        == cumulative_practicals * total_lectures
                        - cumulative_lectures * total_practicals
                    )
                    positive_violation = model.NewIntVar(
                        0,
                        total_lectures * total_practicals,
                        f"progress_positive_{group}_{subject}_{day.isoformat()}_{slot[1]}",
                    )
                    model.AddMaxEquality(positive_violation, [0, violation])
                    penalties.append(
                        positive_violation
                        * PENALTY_PROGRESS_VIOLATION
                        * progression_rule["weight"]
                    )

    # Penalize every empty lesson between the first and last lesson of a group.
    # Using any occupied slot before and after the empty slot also catches
    # double and longer windows, not only occupied-empty-occupied patterns.
    component_groups = sorted(
        {
            group
            for event in events
            for group in event.get("group_resources", event["groups"])
        }
    )
    windows_rule = _rule(context, "minimize_windows", weight=5)
    lunch_rule = _rule(context, "lunch_break", is_hard=True, weight=5)
    for group in component_groups:
        for day, day_slots in by_day.items():
            ordered_slots = sorted(day_slots, key=lambda slot: slot[1])
            occupied: list[cp_model.IntVar] = []
            for slot in ordered_slots:
                slot_variables = by_group_slot.get((group, slot), [])
                occupancy = model.NewBoolVar(
                    f"occupied_{group}_{day.isoformat()}_{slot[1]}"
                )
                if slot_variables:
                    model.Add(occupancy == sum(slot_variables))
                else:
                    model.Add(occupancy == 0)
                occupied.append(occupancy)

            for index in range(1, len(occupied) - 1):
                occupied_before = model.NewBoolVar(
                    f"occupied_before_{group}_{day.isoformat()}_"
                    f"{ordered_slots[index][1]}"
                )
                occupied_after = model.NewBoolVar(
                    f"occupied_after_{group}_{day.isoformat()}_"
                    f"{ordered_slots[index][1]}"
                )
                model.AddMaxEquality(occupied_before, occupied[:index])
                model.AddMaxEquality(occupied_after, occupied[index + 1 :])
                window = model.NewBoolVar(
                    f"window_{group}_{day.isoformat()}_{ordered_slots[index][1]}"
                )
                model.Add(window <= occupied_before)
                model.Add(window <= occupied_after)
                model.Add(window <= 1 - occupied[index])
                model.Add(
                    window >= occupied_before + occupied_after - occupied[index] - 1
                )
                if windows_rule["enabled"]:
                    penalties.append(window * PENALTY_WINDOW * windows_rule["weight"])

            occupancy_by_lesson = {
                slot[1]: occupancy for slot, occupancy in zip(ordered_slots, occupied)
            }
            if (
                lunch_rule["enabled"]
                and lunch_rule["is_hard"]
                and 3 in occupancy_by_lesson
                and 4 in occupancy_by_lesson
            ):
                model.Add(occupancy_by_lesson[3] + occupancy_by_lesson[4] <= 1)
            elif (
                lunch_rule["enabled"]
                and 3 in occupancy_by_lesson
                and 4 in occupancy_by_lesson
            ):
                lunch_violation = model.NewBoolVar(f"lunch_{group}_{day.isoformat()}")
                model.Add(
                    lunch_violation
                    == occupancy_by_lesson[3] + occupancy_by_lesson[4] - 1
                ).OnlyEnforceIf([occupancy_by_lesson[3], occupancy_by_lesson[4]])
                model.Add(lunch_violation == 0).OnlyEnforceIf(
                    occupancy_by_lesson[3].Not()
                )
                model.Add(lunch_violation == 0).OnlyEnforceIf(
                    occupancy_by_lesson[4].Not()
                )
                penalties.append(lunch_violation * 100 * lunch_rule["weight"])

    model.Minimize(sum(penalties))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(context["max_time_seconds"])
    solver.parameters.num_search_workers = int(context.get("num_workers", NUM_WORKERS))
    status = solver.Solve(model)
    elapsed = time.perf_counter() - started_at
    metrics = {
        "events": len(events),
        "groups": len(component_groups),
        "slots": len(slots),
        "variables": len(model.Proto().variables),
        "decision_variables": len(variables),
        "constraints": len(model.Proto().constraints),
        "solve_seconds": round(elapsed, 4),
        "solver_status": solver.StatusName(status),
        "objective": (
            round(solver.ObjectiveValue(), 2)
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            else None
        ),
    }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": "failed",
            "assignments": [],
            "unassigned": [],
            "error": "No feasible component solution",
            "metrics": metrics,
        }

    assignments: list[dict[str, Any]] = []
    unassigned: list[dict[str, Any]] = []
    events_by_id = {event["id"]: event for event in events}
    for (event_id, slot), variable in variables.items():
        if solver.Value(variable):
            event = events_by_id[event_id]
            assignments.append(
                {
                    **event,
                    "slot": [slot[0].isoformat(), slot[1]],
                }
            )
    for event_id, (deficit, target) in deficits.items():
        missing = solver.Value(deficit)
        if missing:
            event = events_by_id[event_id]
            unassigned.append({**event, "missing_count": missing, "target": target})

    return {
        "status": "success",
        "assignments": assignments,
        "unassigned": unassigned,
        "error": None,
        "metrics": metrics,
    }


def assign_rooms_matching(
    assignments: list[dict[str, Any]], context: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Assign rooms globally per slot using a minimum-penalty CP-SAT matching."""
    started_at = time.perf_counter()
    rooms: dict[str, dict[str, Any]] = context["rooms"]
    unavailable = _normalize_unavailable(context.get("unavailable", {}))
    by_slot: dict[tuple[str, int], list[dict[str, Any]]] = collections.defaultdict(list)
    for assignment in assignments:
        by_slot[(assignment["slot"][0], int(assignment["slot"][1]))].append(assignment)

    completed: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    matching_variables = 0
    capacity_rule = _rule(context, "room_capacity", weight=5)
    type_rule = _rule(context, "room_type", weight=5)
    feature_rule = _rule(context, "room_features", weight=7)
    for (date_string, lesson), slot_events in by_slot.items():
        date = datetime.date.fromisoformat(date_string)
        available_rooms = []
        for room_name in sorted(rooms):
            room_slots = unavailable.get("room", {}).get(room_name, set())
            if (date.weekday(), lesson) not in room_slots and (
                date,
                lesson,
            ) not in room_slots:
                available_rooms.append(room_name)

        model = cp_model.CpModel()
        room_variables: dict[tuple[str, str], cp_model.IntVar] = {}
        penalties: list[Any] = []
        for event in slot_events:
            event_id = event["id"]
            event_room_variables = []
            size = sum(
                int(context["group_sizes"].get(group, 20)) for group in event["groups"]
            )
            for room_name in available_rooms:
                room = rooms[room_name]
                capacity_shortfall = max(0, size - int(room["capacity"]))
                room_type = room.get("type")
                type_mismatch = room_type not in {None, "mixed", event["type"]}
                missing_features = set(event.get("required_features", [])) - set(
                    room.get("features", [])
                )
                if event.get("required_room") not in {None, room_name}:
                    continue
                if (
                    capacity_rule["enabled"]
                    and capacity_rule["is_hard"]
                    and capacity_shortfall
                ):
                    continue
                if type_rule["enabled"] and type_rule["is_hard"] and type_mismatch:
                    continue
                if (
                    feature_rule["enabled"]
                    and feature_rule["is_hard"]
                    and missing_features
                ):
                    continue
                variable = model.NewBoolVar(f"room_{event_id}_{room_name}")
                room_variables[(event_id, room_name)] = variable
                event_room_variables.append(variable)
                capacity_excess = max(0, int(room["capacity"]) - size)
                cost = capacity_excess
                if capacity_rule["enabled"]:
                    cost += capacity_shortfall * 100 * capacity_rule["weight"]
                if type_rule["enabled"] and type_mismatch:
                    cost += 200 * type_rule["weight"]
                if feature_rule["enabled"] and missing_features:
                    cost += len(missing_features) * 300 * feature_rule["weight"]
                penalties.append(variable * cost)

            no_room = model.NewBoolVar(f"room_unassigned_{event_id}")
            model.AddExactlyOne(event_room_variables + [no_room])
            penalties.append(no_room * 100_000)

        for room_name in available_rooms:
            model.AddAtMostOne(
                [
                    room_variables[(event["id"], room_name)]
                    for event in slot_events
                    if (event["id"], room_name) in room_variables
                ]
            )

        model.Minimize(sum(penalties))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(
            context.get("room_assignment_max_seconds", 5)
        )
        solver.parameters.num_search_workers = min(
            4, int(context.get("num_workers", 4))
        )
        status = solver.Solve(model)
        matching_variables += len(model.Proto().variables)

        for event in slot_events:
            event_id = event["id"]
            result = dict(event)
            selected_room = (
                next(
                    (
                        room_name
                        for room_name in available_rooms
                        if (event_id, room_name) in room_variables
                        and solver.Value(room_variables[(event_id, room_name)])
                    ),
                    None,
                )
                if status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
                else None
            )
            result["room"] = selected_room or "НЕТ АУДИТОРИИ"
            result["room_ref_id"] = (
                rooms[selected_room].get("id") if selected_room else None
            )

            warning = None
            if selected_room is None:
                warning = "Не хватило аудиторий"
            else:
                room = rooms[selected_room]
                size = sum(
                    int(context["group_sizes"].get(group, 20))
                    for group in event["groups"]
                )
                if int(room["capacity"]) < size:
                    warning = f"Вместимость: {room['capacity']} на {size} чел."
                elif room.get("type") not in {None, "mixed", event["type"]}:
                    warning = f"Тип: {room.get('type')} вместо {event['type']}"
                else:
                    missing_features = set(event.get("required_features", [])) - set(
                        room.get("features", [])
                    )
                    if missing_features:
                        warning = "Нет оснащения: " + ", ".join(
                            sorted(missing_features)
                        )
            result["warning"] = warning
            completed.append(result)
            if warning:
                warnings.append(
                    {
                        "event_id": event_id,
                        "date": date_string,
                        "lesson": lesson,
                        "message": warning,
                    }
                )

    metrics = {
        "slots_with_events": len(by_slot),
        "variables": matching_variables,
        "solve_seconds": round(time.perf_counter() - started_at, 4),
    }
    return completed, warnings, metrics
