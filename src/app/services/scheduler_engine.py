import collections
import datetime
import logging

from core.constants import (
    LOGGING_ENABLED,
    NUM_WORKERS,
    PENALTY_LATE_LESSON,
    PENALTY_MORNING_PRIORITY,
    PENALTY_PROGRESS_VIOLATION,
    PENALTY_SYNC_STREAM,
    PENALTY_UNASSIGNED,
    PENALTY_WINDOW,
)
from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)

TYPE_MAP = {"lec": "lectures", "sem": "seminars", "lab": "labs"}
LESSON_TYPES = ["lec", "sem", "lab"]


def _get_target(subj_data: dict, lesson_type: str) -> int:
    """Get target count for a lesson type from subject data."""
    return subj_data.get(TYPE_MAP[lesson_type], 0)


def generate_slots(
    start_date: datetime.date,
    end_date: datetime.date,
    study_days: list[int],
    lessons: list[int],
    holidays: set[datetime.date],
) -> list[tuple[datetime.date, int]]:
    slots = []
    d = start_date
    while d <= end_date:
        if d.weekday() in study_days and d not in holidays:
            for lesson in lessons:
                slots.append((d, lesson))
        d += datetime.timedelta(days=1)
    return slots


def _build_slot_indices(
    slots: list[tuple[datetime.date, int]], start_date: datetime.date
) -> tuple[dict[datetime.date, list], dict[int, list]]:
    """Build lookup indices for slots by day and by week."""
    slots_by_day = collections.defaultdict(list)
    slots_by_week = collections.defaultdict(list)
    for s in slots:
        slots_by_day[s[0]].append(s)
        week = (s[0] - start_date).days // 7
        slots_by_week[week].append(s)
    return slots_by_day, slots_by_week


def _preprocess_unavailable(unavailable_times: dict) -> dict:
    """Convert unavailable_times lists to sets for O(1) lookup."""
    processed = {}
    for category, items in unavailable_times.items():
        processed[category] = {}
        for name, time_list in items.items():
            processed[category][name] = set(time_list)
    return processed


def _is_slot_blocked(
    teacher: str | None, group: str, slot: tuple[datetime.date, int], unavail: dict
) -> bool:
    """Check if a slot is blocked for a teacher or group."""
    d, lesson = slot
    if teacher and teacher in unavail.get("teacher", {}):
        ts = unavail["teacher"][teacher]
        if (d.weekday(), lesson) in ts or (d, lesson) in ts:
            return True
    if group in unavail.get("group", {}):
        gs = unavail["group"][group]
        if (d.weekday(), lesson) in gs or (d, lesson) in gs:
            return True
    return False


def solve_schedule(
    start_date: datetime.date,
    end_date: datetime.date,
    study_days: list[int],
    lessons: list[int],
    holidays: set[datetime.date],
    groups: list[str],
    group_sizes: dict[str, int],
    subjects: dict[str, dict],
    streams_map: dict[str, list[str]],
    rooms: dict[str, dict],
    unavailable_times: dict,
    fixed_schedules: dict | None = None,
    max_time_seconds: int = 300,
    priorities: dict | None = None,
) -> tuple[list[dict] | None, list[tuple[datetime.date, int]], list[str]]:
    if priorities is None:
        priorities = {}

    model = cp_model.CpModel()
    SLOTS = generate_slots(start_date, end_date, study_days, lessons, holidays)
    if not SLOTS:
        return None, [], ["Нет доступных слотов в выбранном диапазоне дат."]

    days = sorted(set(d for d, _ in SLOTS))
    teachers = set(s["teacher"] for s in subjects.values() if s.get("teacher"))
    fixed_schedules = fixed_schedules or {}

    # --- Pre-computed indices ---
    slots_by_day, slots_by_week = _build_slot_indices(SLOTS, start_date)
    unavail = _preprocess_unavailable(unavailable_times)
    total_weeks = max(1, (end_date - start_date).days // 7 + 1)

    # Index: teacher -> list of subjects they teach
    teacher_subjects = collections.defaultdict(list)
    for subj, subj_data in subjects.items():
        t_name = subj_data.get("teacher")
        if t_name:
            teacher_subjects[t_name].append(subj)

    x = {}  # x[(g, subj, t, s)] — логическая переменная
    penalties = []
    unassigned_vars = {}

    # Index for quick lookup: (group, slot) -> list of x-vars
    vars_by_group_slot = collections.defaultdict(list)

    # --- Variable creation with pre-filtering ---
    for subj, subj_data in subjects.items():
        relevant_groups = streams_map.get(subj, [])
        t_name = subj_data.get("teacher")
        for g in relevant_groups:
            if g not in groups:
                continue
            for t in LESSON_TYPES:
                target_count = _get_target(subj_data, t)
                if target_count == 0:
                    continue
                for s in SLOTS:
                    # Pre-filter: skip slots where teacher/group is unavailable
                    if _is_slot_blocked(t_name, g, s, unavail):
                        continue

                    var = model.NewBoolVar(f"x_{g}_{subj}_{t}_{s[0]}_{s[1]}")
                    x[(g, subj, t, s)] = var
                    vars_by_group_slot[(g, s)].append(var)

                    # Глобальный штраф за поздние пары
                    penalties.append(var * s[1] * PENALTY_LATE_LESSON)

                    # Штраф за приоритет (Утро / День / Вечер)
                    pref = priorities.get(subj, "day")
                    if pref == "morning":
                        if s[1] > 2:
                            penalties.append(
                                var * (s[1] - 2) * PENALTY_MORNING_PRIORITY
                            )
                    elif pref == "evening":
                        if s[1] < 5:
                            penalties.append(
                                var * (5 - s[1]) * PENALTY_MORNING_PRIORITY
                            )

    # 1. Точное количество занятий + дневные/недельные лимиты
    for subj, subj_data in subjects.items():
        relevant_groups = streams_map.get(subj, [])
        for g in relevant_groups:
            if g not in groups:
                continue
            for t in LESSON_TYPES:
                target = _get_target(subj_data, t)
                if target == 0:
                    continue

                vars_for_g_subj_t = [
                    x[(g, subj, t, s)] for s in SLOTS if (g, subj, t, s) in x
                ]
                if not vars_for_g_subj_t:
                    continue

                deficit = model.NewIntVar(0, target, f"def_{g}_{subj}_{t}")
                model.Add(sum(vars_for_g_subj_t) + deficit == target)
                penalties.append(deficit * PENALTY_UNASSIGNED)
                unassigned_vars[(g, subj, t)] = (deficit, target)

                # Недельный лимит (равномерное распределение + запас)
                weekly_limit = (target // total_weeks) + 2
                for _w, week_slots in slots_by_week.items():
                    week_vars = [
                        x[(g, subj, t, s)] for s in week_slots if (g, subj, t, s) in x
                    ]
                    if week_vars:
                        model.Add(sum(week_vars) <= weekly_limit)

                # Дневной лимит: не более 1 занятия каждого типа по предмету в день
                for _day, day_slots in slots_by_day.items():
                    day_vars = [
                        x[(g, subj, t, s)] for s in day_slots if (g, subj, t, s) in x
                    ]
                    if day_vars:
                        model.Add(sum(day_vars) <= 1)

    # 2. Не более одной пары у группы в слот + Определение занятости слота
    has_class = {}
    for g in groups:
        for s in SLOTS:
            events = vars_by_group_slot.get((g, s), [])
            hc = model.NewBoolVar(f"hc_{g}_{s[0]}_{s[1]}")
            if events:
                model.AddExactlyOne(events + [hc.Not()])
            else:
                model.Add(hc == 0)
            has_class[(g, s)] = hc

    # 3. Лекции в потоке (синхронизация)
    for subj, stream_groups in streams_map.items():
        if len(stream_groups) <= 1 or subjects.get(subj, {}).get("lectures", 0) == 0:
            continue
        active_stream = [g for g in stream_groups if g in groups]
        if len(active_stream) < 2:
            continue
        base_g = active_stream[0]
        for other_g in active_stream[1:]:
            for s in SLOTS:
                if (base_g, subj, "lec", s) in x and (other_g, subj, "lec", s) in x:
                    model.Add(
                        x[(base_g, subj, "lec", s)] == x[(other_g, subj, "lec", s)]
                    )

    # 4. Преподаватель может вести только одну пару в слоте
    for s in SLOTS:
        for t_name in teachers:
            t_events = []
            for subj in teacher_subjects[t_name]:
                subj_data = subjects[subj]
                # Семинары и лабораторные уникальны для каждой группы
                for sem_type in ["sem", "lab"]:
                    if _get_target(subj_data, sem_type) > 0:
                        for g in groups:
                            if (g, subj, sem_type, s) in x:
                                t_events.append(x[(g, subj, sem_type, s)])
                # Лекции потоковые — берём только base_g
                if subj_data.get("lectures", 0) > 0:
                    stream = streams_map.get(subj, [])
                    active_stream = [g for g in stream if g in groups]
                    if active_stream:
                        base_g = active_stream[0]
                        if (base_g, subj, "lec", s) in x:
                            t_events.append(x[(base_g, subj, "lec", s)])

            if t_events:
                model.AddAtMostOne(t_events)

    # 5. Доступность — обработана через pre-filtering при создании переменных.
    #    Переменные для заблокированных слотов просто не создаются.

    # 6. Фиксации
    for g, fixes in fixed_schedules.items():
        for f in fixes:
            d_l = (f["date"], f["lesson"])
            subj = f["subject"]
            t = f["type"]
            if (g, subj, t, d_l) in x:
                model.Add(x[(g, subj, t, d_l)] == 1)

    # 7. Дополнительные ограничения

    # 7.2. Синхронизация семинаров по потоку (Soft) — инкрементальные суммы
    for subj, stream_groups in streams_map.items():
        if len(stream_groups) <= 1 or subjects.get(subj, {}).get("seminars", 0) == 0:
            continue
        active_stream = [g for g in stream_groups if g in groups]
        if len(active_stream) < 2:
            continue
        base_g = active_stream[0]
        for other_g in active_stream[1:]:
            cum_base = 0
            cum_other = 0
            for day in days:
                for s in slots_by_day[day]:
                    if (base_g, subj, "sem", s) in x:
                        cum_base = cum_base + x[(base_g, subj, "sem", s)]
                    if (other_g, subj, "sem", s) in x:
                        cum_other = cum_other + x[(other_g, subj, "sem", s)]

                diff = model.NewIntVar(
                    -100, 100, f"diff_sem_{subj}_{base_g}_{other_g}_{day}"
                )
                model.Add(diff == cum_base - cum_other)
                abs_diff = model.NewIntVar(
                    0, 100, f"abs_diff_sem_{subj}_{base_g}_{other_g}_{day}"
                )
                model.AddAbsEquality(abs_diff, diff)
                penalties.append(abs_diff * PENALTY_SYNC_STREAM)

    # 7.3. Окна и Обед (Soft)
    for g in groups:
        for day in days:
            day_slots_sorted = sorted(slots_by_day[day], key=lambda i: i[1])
            hc_day = [has_class[(g, s)] for s in day_slots_sorted]
            if not hc_day:
                continue

            total_classes = sum(hc_day)
            day_active = model.NewBoolVar(f"active_{g}_{day}")
            model.Add(total_classes > 0).OnlyEnforceIf(day_active)
            model.Add(total_classes == 0).OnlyEnforceIf(day_active.Not())

            start_idx = model.NewIntVar(1, 10, f"start_{g}_{day}")
            end_idx = model.NewIntVar(1, 10, f"end_{g}_{day}")
            for idx, lesson_hc in enumerate(hc_day):
                l_num = day_slots_sorted[idx][1]
                model.Add(start_idx <= l_num).OnlyEnforceIf(lesson_hc)
                model.Add(end_idx >= l_num).OnlyEnforceIf(lesson_hc)

            # Обед (пересечение 3 и 4 пары)
            start_le_3 = model.NewBoolVar(f"start_le_3_{g}_{day}")
            model.Add(start_idx <= 3).OnlyEnforceIf(start_le_3)
            model.Add(start_idx > 3).OnlyEnforceIf(start_le_3.Not())

            end_ge_4 = model.NewBoolVar(f"end_ge_4_{g}_{day}")
            model.Add(end_idx >= 4).OnlyEnforceIf(end_ge_4)
            model.Add(end_idx < 4).OnlyEnforceIf(end_ge_4.Not())

            crosses_lunch = model.NewBoolVar(f"crosses_lunch_{g}_{day}")
            model.AddMinEquality(crosses_lunch, [start_le_3, end_ge_4])

            windows = model.NewIntVar(0, 10, f"windows_{g}_{day}")
            model.Add(
                windows == end_idx - start_idx + 1 - total_classes - crosses_lunch
            ).OnlyEnforceIf(day_active)
            model.Add(windows == 0).OnlyEnforceIf(day_active.Not())
            penalties.append(windows * PENALTY_WINDOW)

            # Обед (ЖЕСТКОЕ ПРАВИЛО: нельзя занимать и 3, и 4 пару одновременно)
            idx_3 = next((i for i, s in enumerate(day_slots_sorted) if s[1] == 3), None)
            idx_4 = next((i for i, s in enumerate(day_slots_sorted) if s[1] == 4), None)
            if idx_3 is not None and idx_4 is not None:
                model.AddBoolOr([hc_day[idx_3].Not(), hc_day[idx_4].Not()])

    # 7.4. Синхронизация Лекции -> Семинары (Soft) — инкрементальные суммы
    for subj, subj_data in subjects.items():
        if subj_data.get("lectures", 0) == 0 or subj_data.get("seminars", 0) == 0:
            continue
        total_lec = subj_data["lectures"]
        total_sem = subj_data["seminars"]
        stream = streams_map.get(subj, [])
        active_stream = [g for g in stream if g in groups]
        if not active_stream:
            continue
        base_g = active_stream[0]

        # Precompute which groups actually have seminar variables
        groups_with_sems = [
            g for g in active_stream if any((g, subj, "sem", s) in x for s in SLOTS)
        ]

        # Build incremental cumulative sums per group
        cum_sems = {g: 0 for g in groups_with_sems}
        cum_lec = 0
        for day in days:
            for s in slots_by_day[day]:
                if (base_g, subj, "lec", s) in x:
                    cum_lec = cum_lec + x[(base_g, subj, "lec", s)]

            for g in groups_with_sems:
                for s in slots_by_day[day]:
                    if (g, subj, "sem", s) in x:
                        cum_sems[g] = cum_sems[g] + x[(g, subj, "sem", s)]

                # Proportion of lectures should be >= proportion of seminars
                # cum_lec / total_lec >= cum_sem / total_sem
                # => cum_lec * total_sem >= cum_sem * total_lec
                viol = model.NewIntVar(-1000, 1000, f"viol_{subj}_{g}_{day}")
                model.Add(viol == cum_sems[g] * total_lec - cum_lec * total_sem)
                viol_pos = model.NewIntVar(0, 1000, f"viol_pos_{subj}_{g}_{day}")
                model.AddMaxEquality(viol_pos, [0, viol])
                penalties.append(viol_pos * PENALTY_PROGRESS_VIOLATION)

    model.Minimize(sum(penalties))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_time_seconds
    solver.parameters.num_search_workers = NUM_WORKERS

    num_vars = len(x)
    (
        model.Proto().constraints.__len__()
        if hasattr(model.Proto().constraints, "__len__")
        else "?"
    )
    logger.info(
        f"[ENGINE] Модель: {len(groups)} групп, {len(subjects)} предметов, "
        f"{len(SLOTS)} слотов, {num_vars} переменных"
    )

    if LOGGING_ENABLED:
        solver.parameters.log_search_progress = True

    status = solver.Solve(model)

    logger.info(f"[ENGINE] Статус решения: {solver.StatusName(status)}")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        logger.info(
            f"[ENGINE] Найдено решение. Целевая функция: {solver.ObjectiveValue()}"
        )
        schedule = []
        for (g, subj, t, s), var in x.items():
            if solver.Value(var) == 1:
                schedule.append(
                    {
                        "group": g,
                        "subject": subj,
                        "type": t,
                        "slot": s,
                        "teacher": subjects[subj]["teacher"],
                        "teacher_id": subjects[subj].get("teacher_id"),
                    }
                )

        unassigned_warnings = []
        logger.info("=" * 40)
        logger.info("ОТЧЕТ ПО НЕВЫСТАВЛЕННЫМ ПАРАМ:")
        for (g, subj, t), (deficit_var, target) in unassigned_vars.items():
            val = solver.Value(deficit_var)
            if val > 0:
                type_name = (
                    "Лекция"
                    if t == "lec"
                    else ("Лабораторная" if t == "lab" else "Семинар")
                )
                msg = (
                    f"Группа {g}: не выставлено {val} из {target} "
                    f"пар ({subj}, {type_name})"
                )
                logger.warning(f" [!] {msg}")
                unassigned_warnings.append(
                    {"group": g, "subject": subj, "type": t, "msg": msg, "count": val}
                )

        if not unassigned_warnings:
            logger.info(" Все пары успешно выставлены!")
        logger.info("=" * 40)

        # Phase 2: Rooms (Greedy)
        final_schedule, room_warnings = assign_rooms(
            schedule, SLOTS, rooms, group_sizes, subjects, unavailable_times
        )
        return final_schedule, SLOTS, unassigned_warnings + room_warnings
    else:
        return None, SLOTS, ["Решение не найдено. Слишком жесткие ограничения."]


def assign_rooms(
    schedule: list[dict],
    SLOTS: list[tuple[datetime.date, int]],
    rooms: dict[str, dict],
    group_sizes: dict[str, int],
    subjects: dict[str, dict],
    unavailable_times: dict,
) -> tuple[list[dict], list[dict]]:
    final_schedule = []
    warnings = []
    by_slot = collections.defaultdict(list)
    for entry in schedule:
        by_slot[entry["slot"]].append(entry)

    for s in SLOTS:
        day_events = by_slot[s]
        if not day_events:
            continue

        events = []
        # Group-specific activities
        for ev in day_events:
            if ev["type"] in {"sem", "lab"}:
                size = group_sizes.get(ev["group"], 20)
                events.append(
                    {
                        "subject": ev["subject"],
                        "type": ev["type"],
                        "groups": [ev["group"]],
                        "size": size,
                        "original": [ev],
                    }
                )
        # Lectures
        lec_grouped = collections.defaultdict(list)
        for ev in [e for e in day_events if e["type"] == "lec"]:
            lec_grouped[ev["subject"]].append(ev)
        for subj, evs in lec_grouped.items():
            size = sum(group_sizes.get(e["group"], 20) for e in evs)
            events.append(
                {
                    "subject": subj,
                    "type": "lec",
                    "groups": [e["group"] for e in evs],
                    "size": size,
                    "original": evs,
                }
            )

        events.sort(key=lambda x: x["size"], reverse=True)
        available_rooms = set(rooms.keys())

        # Room unavailability
        for r_name in list(available_rooms):
            if r_name in unavailable_times.get("room", {}):
                if (s[0].weekday(), s[1]) in unavailable_times["room"][r_name]:
                    available_rooms.discard(r_name)

        for ev in events:
            best_room = None
            best_score = -9999
            target_type = ev["type"]

            for r in available_rooms:
                r_data = rooms[r]
                score = 0
                if r_data["type"] == target_type:
                    score += 100
                cap_diff = r_data["capacity"] - ev["size"]
                if cap_diff >= 0:
                    score += 50 - cap_diff
                else:
                    score -= 500
                if score > best_score:
                    best_score = score
                    best_room = r

            if best_room:
                available_rooms.remove(best_room)
                r_data = rooms[best_room]
                w_msg = None
                if r_data["capacity"] < ev["size"]:
                    w_msg = f"Вместимость: {r_data['capacity']} на {ev['size']} чел."
                elif r_data["type"] != target_type:
                    w_msg = f"Тип: {r_data['type']} вместо {target_type}"

                for orig in ev["original"]:
                    cp = dict(orig)
                    cp["room"] = best_room
                    if w_msg:
                        cp["warning"] = w_msg
                        warnings.append(
                            {
                                "date": s[0],
                                "lesson": s[1],
                                "group": cp["group"],
                                "subject": cp["subject"],
                                "msg": w_msg,
                            }
                        )
                    final_schedule.append(cp)
            else:
                for orig in ev["original"]:
                    cp = dict(orig)
                    cp["room"] = "НЕТ АУДИТОРИИ"
                    cp["warning"] = "Не хватило аудиторий"
                    warnings.append(
                        {
                            "date": s[0],
                            "lesson": s[1],
                            "group": cp["group"],
                            "subject": cp["subject"],
                            "msg": "Нет аудитории",
                        }
                    )
                    final_schedule.append(cp)

    return final_schedule, warnings
