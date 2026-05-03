import collections
import datetime

from ortools.sat.python import cp_model


def generate_slots(start_date, end_date, study_days, lessons, holidays):
    slots = []
    d = start_date
    while d <= end_date:
        if d.weekday() in study_days and d not in holidays:
            for lesson in lessons:
                slots.append((d, lesson))
        d += datetime.timedelta(days=1)
    return slots


def solve_schedule(
        start_date,
        end_date,
        study_days,
        lessons,
        holidays,
        groups,
        group_sizes,
        subjects,
        streams_map,
        rooms,
        unavailable_times,
        fixed_schedules=None,
        max_time_seconds=300
):
    model = cp_model.CpModel()
    SLOTS = generate_slots(start_date, end_date, study_days, lessons, holidays)
    if not SLOTS:
        return None, [], ["Нет доступных слотов в выбранном диапазоне дат."]

    days = sorted(set(d for d, _ in SLOTS))
    teachers = set(s["teacher"] for s in subjects.values() if s.get("teacher"))
    fixed_schedules = fixed_schedules or {}

    x = {}  # x[(g, subj, t, s)] — логическая переменная
    penalties = []
    unassigned_vars = {}

    for g in groups:
        for subj, subj_data in subjects.items():
            for t in ["lec", "sem"]:
                target_count = subj_data.get("lectures", 0) if t == "lec" else subj_data.get("seminars", 0)
                if target_count == 0:
                    continue
                for s in SLOTS:
                    var = model.NewBoolVar(f"x_{g}_{subj}_{t}_{s[0]}_{s[1]}")
                    x[(g, subj, t, s)] = var

                    # Штраф за поздние пары
                    penalties.append(var * s[1] * 3)

                    # Штраф за субботу (weekday == 5)
                    if s[0].weekday() == 5:
                        penalties.append(var * 60)

    # 1. Количество занятий
    for g in groups:
        for subj, subj_data in subjects.items():
            for t in ["lec", "sem"]:
                target_count = subj_data.get("lectures", 0) if t == "lec" else subj_data.get("seminars", 0)
                if target_count == 0:
                    continue
                deficit = model.NewIntVar(0, target_count, f"deficit_{g}_{subj}_{t}")
                model.Add(sum([x[(g, subj, t, s)] for s in SLOTS if (g, subj, t, s) in x]) + deficit == target_count)
                unassigned_vars[(g, subj, t)] = (deficit, target_count)
                penalties.append(deficit * 100000)

    # 2. Не более одной пары у группы в слот
    for g in groups:
        for s in SLOTS:
            events = []
            for subj, subj_data in subjects.items():
                if (g, subj, "lec", s) in x: events.append(x[(g, subj, "lec", s)])
                if (g, subj, "sem", s) in x: events.append(x[(g, subj, "sem", s)])

            if events:
                model.AddAtMostOne(events)

    # 3. Лекции в потоке
    for subj, stream_groups in streams_map.items():
        if len(stream_groups) > 1 and subjects.get(subj, {}).get("lectures", 0) > 0:
            base_g = stream_groups[0]
            for other_g in stream_groups[1:]:
                if other_g in groups:
                    for s in SLOTS:
                        if (base_g, subj, "lec", s) in x and (other_g, subj, "lec", s) in x:
                            model.Add(x[(base_g, subj, "lec", s)] == x[(other_g, subj, "lec", s)])

    # 4. Преподаватель может вести только одну пару
    for s in SLOTS:
        for t_name in teachers:
            t_events = []
            for subj, subj_data in subjects.items():
                if subj_data.get("teacher") == t_name:
                    if subj_data.get("seminars", 0) > 0:
                        for g in groups:
                            if (g, subj, "sem", s) in x:
                                t_events.append(x[(g, subj, "sem", s)])

                    if subj_data.get("lectures", 0) > 0:
                        stream = streams_map.get(subj, [groups[0]])
                        base_g = stream[0]
                        if (base_g, subj, "lec", s) in x:
                            t_events.append(x[(base_g, subj, "lec", s)])

            if t_events:
                model.AddAtMostOne(t_events)

    # 5. Доступность
    for g in groups:
        for subj, subj_data in subjects.items():
            t_name = subj_data.get("teacher")
            for t in ["lec", "sem"]:
                if (g, subj, t, SLOTS[0]) not in x: continue
                for s in SLOTS:
                    var = x[(g, subj, t, s)]
                    d, lesson = s

                    # Преподаватель
                    if t_name and t_name in unavailable_times.get("teacher", {}):
                        if (d.weekday(), lesson) in unavailable_times["teacher"][t_name]:
                            model.Add(var == 0)
                            continue

                    # Группа
                    if g in unavailable_times.get("group", {}):
                        if (d.weekday(), lesson) in unavailable_times["group"][g]:
                            model.Add(var == 0)

    # 6. Фиксации
    for g, fixes in fixed_schedules.items():
        for f in fixes:
            d_l = (f["date"], f["lesson"])
            subj = f["subject"]
            t = f["type"]
            if (g, subj, t, d_l) in x:
                model.Add(x[(g, subj, t, d_l)] == 1)

    model.Minimize(sum(penalties))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_time_seconds
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        schedule = []
        for (g, subj, t, s), var in x.items():
            if solver.Value(var) == 1:
                schedule.append(
                    {"group": g, "subject": subj, "type": t, "slot": s, "teacher": subjects[subj]["teacher"]})

        unassigned_warnings = []
        for (g, subj, t), (deficit_var, target) in unassigned_vars.items():
            val = solver.Value(deficit_var)
            if val > 0:
                unassigned_warnings.append(
                    {"group": g, "subject": subj, "type": t, "msg": f"Не удалось выставить {val} из {target} пар"})

        # Phase 2: Rooms (Greedy)
        final_schedule, room_warnings = assign_rooms(schedule, SLOTS, rooms, group_sizes, subjects, unavailable_times)
        return final_schedule, SLOTS, unassigned_warnings + room_warnings
    else:
        return None, SLOTS, ["Решение не найдено. Слишком жесткие ограничения."]


def assign_rooms(schedule, SLOTS, rooms, group_sizes, subjects, unavailable_times):
    final_schedule = []
    warnings = []
    by_slot = collections.defaultdict(list)
    for entry in schedule:
        by_slot[entry["slot"]].append(entry)

    for s in SLOTS:
        day_events = by_slot[s]
        if not day_events: continue

        events = []
        # Seminars
        for ev in day_events:
            if ev["type"] == "sem":
                size = group_sizes.get(ev["group"], 20)
                events.append({"subject": ev["subject"], "type": ev["type"], "groups": [ev["group"]], "size": size,
                               "original": [ev]})
        # Lectures
        lec_grouped = collections.defaultdict(list)
        for ev in [e for e in day_events if e["type"] == "lec"]:
            lec_grouped[ev["subject"]].append(ev)
        for subj, evs in lec_grouped.items():
            size = sum(group_sizes.get(e["group"], 20) for e in evs)
            events.append(
                {"subject": subj, "type": "lec", "groups": [e["group"] for e in evs], "size": size, "original": evs})

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
            target_type = "lec" if ev["type"] == "lec" else subjects[ev["subject"]].get("type_sem", "sem")

            for r in available_rooms:
                r_data = rooms[r]
                score = 0
                if r_data["type"] == target_type: score += 100
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
                        warnings.append({"date": s[0], "lesson": s[1], "group": cp["group"], "subject": cp["subject"],
                                         "msg": w_msg})
                    final_schedule.append(cp)
            else:
                for orig in ev["original"]:
                    cp = dict(orig)
                    cp["room"] = "НЕТ АУДИТОРИИ"
                    cp["warning"] = "Не хватило аудиторий"
                    warnings.append({"date": s[0], "lesson": s[1], "group": cp["group"], "subject": cp["subject"],
                                     "msg": "Нет аудитории"})
                    final_schedule.append(cp)

    return final_schedule, warnings
