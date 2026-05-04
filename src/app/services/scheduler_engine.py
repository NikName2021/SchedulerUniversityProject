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

    from core.constants import (
        PENALTY_UNASSIGNED, PENALTY_LATE_LESSON, PENALTY_SATURDAY,
        PENALTY_WINDOW, PENALTY_SYNC_STREAM, PENALTY_PROGRESS_VIOLATION
    )

    x = {}  # x[(g, subj, t, s)] — логическая переменная
    penalties = []
    unassigned_vars = {}

    # 0. Инициализация переменных
    for subj, subj_data in subjects.items():
        relevant_groups = streams_map.get(subj, [])
        for g in relevant_groups:
            if g not in groups: continue
            for t in ["lec", "sem"]:
                target_count = subj_data.get("lectures", 0) if t == "lec" else subj_data.get("seminars", 0)
                if target_count == 0:
                    continue
                for s in SLOTS:
                    var = model.NewBoolVar(f"x_{g}_{subj}_{t}_{s[0]}_{s[1]}")
                    x[(g, subj, t, s)] = var
                    
                    # Штраф за поздние пары
                    penalties.append(var * s[1] * PENALTY_LATE_LESSON)

                    # Штраф за субботу
                    if s[0].weekday() == 5:
                        penalties.append(var * PENALTY_SATURDAY)

    # 1. Точное количество занятий (с возможностью "не поставить" со штрафом)
    for subj, subj_data in subjects.items():
        relevant_groups = streams_map.get(subj, [])
        for g in relevant_groups:
            if g not in groups: continue
            for t in ["lec", "sem"]:
                target_count = subj_data.get("lectures", 0) if t == "lec" else subj_data.get("seminars", 0)
                if target_count == 0:
                    continue
                
                vars_for_g_subj_t = [x[(g, subj, t, s)] for s in SLOTS if (g, subj, t, s) in x]
                if not vars_for_g_subj_t: continue
                
                deficit = model.NewIntVar(0, target_count, f"deficit_{g}_{subj}_{t}")
                model.Add(sum(vars_for_g_subj_t) + deficit == target_count)
                unassigned_vars[(g, subj, t)] = (deficit, target_count)
                penalties.append(deficit * PENALTY_UNASSIGNED)

    # 2. Не более одной пары у группы в слот + Определение занятости слота
    has_class = {}
    for g in groups:
        for s in SLOTS:
            events = []
            for subj in subjects.keys():
                if (g, subj, "lec", s) in x: events.append(x[(g, subj, "lec", s)])
                if (g, subj, "sem", s) in x: events.append(x[(g, subj, "sem", s)])
            
            hc = model.NewBoolVar(f"hc_{g}_{s[0]}_{s[1]}")
            if events:
                model.AddExactlyOne(events + [hc.Not()])
            else:
                model.Add(hc == 0)
            has_class[(g, s)] = hc

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
                    # Семинары уникальны
                    if subj_data.get("seminars", 0) > 0:
                        for g in groups:
                            if (g, subj, "sem", s) in x:
                                t_events.append(x[(g, subj, "sem", s)])
                    # Лекции потоковые
                    if subj_data.get("lectures", 0) > 0:
                        stream = streams_map.get(subj, [])
                        if stream:
                            base_g = stream[0]
                            if (base_g, subj, "lec", s) in x:
                                t_events.append(x[(base_g, subj, "lec", s)])

            if t_events:
                model.AddAtMostOne(t_events)

    # 5. Доступность (Хард)
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
                        teacher_unavail = unavailable_times["teacher"][t_name]
                        if (d.weekday(), lesson) in teacher_unavail or (d, lesson) in teacher_unavail:
                            model.Add(var == 0)
                    # Группа
                    if g in unavailable_times.get("group", {}):
                        group_unavail = unavailable_times["group"][g]
                        if (d.weekday(), lesson) in group_unavail or (d, lesson) in group_unavail:
                            model.Add(var == 0)

    # 6. Фиксации
    for g, fixes in fixed_schedules.items():
        for f in fixes:
            d_l = (f["date"], f["lesson"])
            subj = f["subject"]
            t = f["type"]
            if (g, subj, t, d_l) in x:
                model.Add(x[(g, subj, t, d_l)] == 1)

    # 7. Дополнительные ограничения из GPT алгоритма
    
    # 7.1. Не более одной лекции и одной практики в день по одному предмету (Hard)
    for g in groups:
        for subj in subjects.keys():
            for day in days:
                day_slots = [s for s in SLOTS if s[0] == day]
                lec_vars = [x[(g, subj, "lec", s)] for s in day_slots if (g, subj, "lec", s) in x]
                if lec_vars: model.Add(sum(lec_vars) <= 1)
                sem_vars = [x[(g, subj, "sem", s)] for s in day_slots if (g, subj, "sem", s) in x]
                if sem_vars: model.Add(sum(sem_vars) <= 1)

    # 7.2. Синхронизация семинаров по потоку (Soft)
    for subj, stream_groups in streams_map.items():
        if len(stream_groups) > 1 and subjects.get(subj, {}).get("seminars", 0) > 0:
            base_g = stream_groups[0]
            if base_g in groups:
                for other_g in stream_groups[1:]:
                    if other_g in groups:
                        for day in days:
                            # Кумулятивное количество семинаров к концу дня
                            cum_sem_base = sum(x[(base_g, subj, "sem", s)] for s in SLOTS if s[0] <= day and (base_g, subj, "sem", s) in x)
                            cum_sem_other = sum(x[(other_g, subj, "sem", s)] for s in SLOTS if s[0] <= day and (other_g, subj, "sem", s) in x)
                            
                            diff = model.NewIntVar(-100, 100, f"diff_sem_{subj}_{base_g}_{other_g}_{day}")
                            model.Add(diff == cum_sem_base - cum_sem_other)
                            abs_diff = model.NewIntVar(0, 100, f"abs_diff_sem_{subj}_{base_g}_{other_g}_{day}")
                            model.AddAbsEquality(abs_diff, diff)
                            penalties.append(abs_diff * PENALTY_SYNC_STREAM)

    # 7.3. Окна и Обед (Soft)
    for g in groups:
        for day in days:
            day_slots_sorted = sorted([s for s in SLOTS if s[0] == day], key=lambda i: i[1])
            hc_day = [has_class[(g, s)] for s in day_slots_sorted]
            if not hc_day: continue
            
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
            # В gpt.py это было реализовано через crosses_lunch
            start_le_3 = model.NewBoolVar(f"start_le_3_{g}_{day}")
            model.Add(start_idx <= 3).OnlyEnforceIf(start_le_3)
            model.Add(start_idx > 3).OnlyEnforceIf(start_le_3.Not())
            
            end_ge_4 = model.NewBoolVar(f"end_ge_4_{g}_{day}")
            model.Add(end_idx >= 4).OnlyEnforceIf(end_ge_4)
            model.Add(end_idx < 4).OnlyEnforceIf(end_ge_4.Not())
            
            crosses_lunch = model.NewBoolVar(f"crosses_lunch_{g}_{day}")
            model.AddMinEquality(crosses_lunch, [start_le_3, end_ge_4])
            
            windows = model.NewIntVar(0, 10, f"windows_{g}_{day}")
            model.Add(windows == end_idx - start_idx + 1 - total_classes - crosses_lunch).OnlyEnforceIf(day_active)
            model.Add(windows == 0).OnlyEnforceIf(day_active.Not())
            penalties.append(windows * PENALTY_WINDOW)

            # Обед (ЖЕСТКОЕ ПРАВИЛО: нельзя занимать и 3, и 4 пару одновременно)
            # Находим индексы 3 и 4 пары в hc_day
            idx_3 = next((i for i, s in enumerate(day_slots_sorted) if s[1] == 3), None)
            idx_4 = next((i for i, s in enumerate(day_slots_sorted) if s[1] == 4), None)
            if idx_3 is not None and idx_4 is not None:
                model.AddBoolOr([hc_day[idx_3].Not(), hc_day[idx_4].Not()])

    # 7.4. Синхронизация Лекции -> Семинары (Soft)
    for subj, subj_data in subjects.items():
        if subj_data.get("lectures", 0) > 0 and subj_data.get("seminars", 0) > 0:
            total_lec = subj_data["lectures"]
            total_sem = subj_data["seminars"]
            stream = streams_map.get(subj, [])
            if not stream: continue
            base_g = stream[0]
            
            cum_lec = 0
            for day in days:
                day_lecs = sum(x[(base_g, subj, "lec", s)] for s in SLOTS if s[0] == day and (base_g, subj, "lec", s) in x)
                cum_lec += day_lecs
                for g in stream:
                    if g not in groups: continue
                    if (g, subj, "sem", SLOTS[0]) not in x: continue
                    cum_sem = sum(x[(g, subj, "sem", s)] for s in SLOTS if s[0] <= day and (g, subj, "sem", s) in x)
                    
                    # Пропорция лекций должна быть >= пропорции семинаров
                    # cum_lec / total_lec >= cum_sem / total_sem  => cum_lec * total_sem >= cum_sem * total_lec
                    viol = model.NewIntVar(-1000, 1000, f"viol_{subj}_{g}_{day}")
                    model.Add(viol == cum_sem * total_lec - cum_lec * total_sem)
                    viol_pos = model.NewIntVar(0, 1000, f"viol_pos_{subj}_{g}_{day}")
                    model.AddMaxEquality(viol_pos, [0, viol])
                    penalties.append(viol_pos * PENALTY_PROGRESS_VIOLATION)

    model.Minimize(sum(penalties))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_time_seconds
    from core.constants import NUM_WORKERS, LOGGING_ENABLED
    solver.parameters.num_search_workers = NUM_WORKERS
    
    if LOGGING_ENABLED:
        print(f"[ENGINE] Инициализация решения: {len(groups)} групп, {len(subjects)} предметов, {len(SLOTS)} слотов")
    
    status = solver.Solve(model)
    
    if LOGGING_ENABLED:
        print(f"[ENGINE] Статус решения: {solver.StatusName(status)}")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if LOGGING_ENABLED:
            print(f"[ENGINE] Найдено решение. Целевая функция: {solver.ObjectiveValue()}")
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
