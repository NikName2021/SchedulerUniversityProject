import datetime
import collections
from ortools.sat.python import cp_model

from consts_clean import (START, END, LESSONS, STUDY_DAYS, HOLIDAYS, GROUPS, GROUP_SIZES, 
                    subjects, STREAMS, ROOMS, UNAVAILABLE_TIMES, FIXED_SCHEDULES, is_valid)
from draw import save

# =========================
# ГЕНЕРАЦИЯ СЛОТОВ
# =========================
def generate_slots():
    slots = []
    d = START
    while d <= END:
        # Учебные дни
        if d.weekday() in STUDY_DAYS and d not in HOLIDAYS:
            for lesson in LESSONS:
                slots.append((d, lesson))
        d += datetime.timedelta(days=1)
    return slots

# =========================
# ЭТАП 1: ВРЕМЯ И ПРЕПОДАВАТЕЛЬ (CP-SAT)
# =========================
def solve_time_schedule():
    model = cp_model.CpModel()
    SLOTS = generate_slots()
    days = sorted(set(d for d, _ in SLOTS))
    teachers = set(s["teacher"] for s in subjects.values())

    x = {} # x[(g, subj, t, s)] — логическая переменная
    penalties = []
    unassigned_vars = {}

    for g in GROUPS:
        for subj, subj_data in subjects.items():
            for t in ["lec", "sem"]:
                target_count = subj_data["lectures"] if t == "lec" else subj_data["seminars"]
                if target_count == 0:
                    continue
                for s in SLOTS:
                    var = model.NewBoolVar(f"x_{g}_{subj}_{t}_{s[0]}_{s[1]}")
                    x[(g, subj, t, s)] = var
                    
                    # Штраф за поздние пары (чем больше номер пары, тем выше штраф)
                    penalties.append(var * s[1] * 3)
                    
                    # Штраф за субботу (weekday == 5)
                    if s[0].weekday() == 5:
                        penalties.append(var * 60)

    # 1. Точное количество занятий (с возможностью "не поставить" со штрафом)
    for g in GROUPS:
        for subj, subj_data in subjects.items():
            for t in ["lec", "sem"]:
                target_count = subj_data["lectures"] if t == "lec" else subj_data["seminars"]
                if target_count == 0:
                    continue
                deficit = model.NewIntVar(0, target_count, f"deficit_{g}_{subj}_{t}")
                model.Add(sum([x[(g, subj, t, s)] for s in SLOTS]) + deficit == target_count)
                unassigned_vars[(g, subj, t)] = (deficit, target_count)
                # Огромный штраф, чтобы пара отваливалась только если вообще некуда поставить
                penalties.append(deficit * 100000)

    # 2. Не более одной пары у группы в слот
    has_class = {}
    for g in GROUPS:
        for s in SLOTS:
            events = []
            for subj, subj_data in subjects.items():
                if subj_data["lectures"] > 0: events.append(x[(g, subj, "lec", s)])
                if subj_data["seminars"] > 0: events.append(x[(g, subj, "sem", s)])
            
            hc = model.NewBoolVar(f"hc_{g}_{s[0]}_{s[1]}")
            model.AddExactlyOne(events + [hc.Not()])
            has_class[(g, s)] = hc

    # 3. Лекции в потоке
    for subj, stream_groups in STREAMS.items():
        if len(stream_groups) > 1 and subjects[subj]["lectures"] > 0:
            base_g = stream_groups[0]
            for other_g in stream_groups[1:]:
                if other_g in GROUPS:
                    for s in SLOTS:
                        if (base_g, subj, "lec", s) in x and (other_g, subj, "lec", s) in x:
                            model.Add(x[(base_g, subj, "lec", s)] == x[(other_g, subj, "lec", s)])

    # 4. Преподаватель может вести только одну пару
    for s in SLOTS:
        for t_name in teachers:
            t_events = []
            for subj, subj_data in subjects.items():
                if subj_data["teacher"] == t_name:
                    # Семинары уникальны для каждой группы
                    for g in GROUPS:
                        if subj_data["seminars"] > 0:
                            t_events.append(x[(g, subj, "sem", s)])
                    
                    # Лекции ведутся для потока как одно занятие. Берем только первую группу из потока
                    if subj_data["lectures"] > 0:
                        stream = STREAMS.get(subj, [GROUPS[0] if GROUPS else []])
                        base_g = stream[0] if stream else GROUPS[0]
                        if (base_g, subj, "lec", s) in x:
                            t_events.append(x[(base_g, subj, "lec", s)])

            model.AddAtMostOne(t_events)

    # 5. Заблокированное время и доступность (Hard)
    for g in GROUPS:
        for subj, subj_data in subjects.items():
            t_name = subj_data["teacher"]
            for t in ["lec", "sem"]:
                if (g, subj, t, SLOTS[0]) not in x: continue
                for s in SLOTS:
                    var = x[(g, subj, t, s)]
                    d, lesson = s
                    
                    # Старая проверочная функция
                    if not is_valid(t_name, s):
                        model.Add(var == 0)
                        continue
                    
                    # Новая таблица недоступности
                    if "teacher" in UNAVAILABLE_TIMES and t_name in UNAVAILABLE_TIMES["teacher"]:
                        if (d.weekday(), lesson) in UNAVAILABLE_TIMES["teacher"][t_name]:
                            model.Add(var == 0)
                            continue
                            
                    if "group" in UNAVAILABLE_TIMES and g in UNAVAILABLE_TIMES["group"]:
                        if (d.weekday(), lesson) in UNAVAILABLE_TIMES["group"][g]:
                            model.Add(var == 0)

    # 6. Фиксации
    for g, fixes in FIXED_SCHEDULES.items():
        for f in fixes:
            d_l = (f["date"], f["lesson"])
            subj = f["subject"]
            t = f["type"]
            if (g, subj, t, d_l) in x:
                model.Add(x[(g, subj, t, d_l)] == 1)

    # 7. Не более одной лекции и одной практики в день по одному предмету
    for g in GROUPS:
        for subj in subjects.keys():
            for day in days:
                day_slots = [s for s in SLOTS if s[0] == day]
                
                # Лекции
                lec_vars = [x[(g, subj, "lec", s)] for s in day_slots if (g, subj, "lec", s) in x]
                if lec_vars:
                    model.Add(sum(lec_vars) <= 1)
                    
                # Семинары/практики
                sem_vars = [x[(g, subj, "sem", s)] for s in day_slots if (g, subj, "sem", s) in x]
                if sem_vars:
                    model.Add(sum(sem_vars) <= 1)

    # =========================
    # МЯГКИЕ ОГРАНИЧЕНИЯ (SOFT)
    # =========================

    # Синхронизация семинаров по потоку (группы одного направления)
    for subj, stream_groups in STREAMS.items():
        if len(stream_groups) > 1 and subjects[subj]["seminars"] > 0:
            base_g = stream_groups[0]
            if base_g in GROUPS:
                for other_g in stream_groups[1:]:
                    if other_g in GROUPS:
                        for day in days:
                            cum_sem_base = sum(x[(base_g, subj, "sem", s)] for s in SLOTS if s[0] <= day and (base_g, subj, "sem", s) in x)
                            cum_sem_other = sum(x[(other_g, subj, "sem", s)] for s in SLOTS if s[0] <= day and (other_g, subj, "sem", s) in x)
                            
                            diff = model.NewIntVar(-1000, 1000, f"diff_sem_{subj}_{base_g}_{other_g}_{day}")
                            model.Add(diff == cum_sem_base - cum_sem_other)
                            
                            abs_diff = model.NewIntVar(0, 1000, f"abs_diff_sem_{subj}_{base_g}_{other_g}_{day}")
                            model.AddAbsEquality(abs_diff, diff)
                            
                            penalties.append(abs_diff * 10) # Штраф за каждое отставание

    # Распределение окон (Windows) и обед (Lunch)
    for g in GROUPS:
        for day in days:
            day_slots = sorted([s for s in SLOTS if s[0] == day], key=lambda i: i[1])
            hc_day = [has_class[(g, s)] for s in day_slots]
            
            # Если нет слотов в этот день
            if not hc_day: continue
            
            day_active = model.NewBoolVar(f"active_{g}_{day}")
            total_classes = sum(hc_day)
            model.Add(total_classes > 0).OnlyEnforceIf(day_active)
            model.Add(total_classes == 0).OnlyEnforceIf(day_active.Not())
            
            start_idx = model.NewIntVar(1, 6, f"start_{g}_{day}")
            end_idx = model.NewIntVar(1, 6, f"end_{g}_{day}")
            
            # Если активен, start <= lesson, end >= lesson
            for l in range(1, len(hc_day)+1):
                model.Add(start_idx <= l).OnlyEnforceIf(hc_day[l-1])
                model.Add(end_idx >= l).OnlyEnforceIf(hc_day[l-1])
            
            # Обед не считается окном - вычитаем 1, если расписание пересекает 3 и 4 пару
            start_le_3 = model.NewBoolVar(f"start_le_3_{g}_{day}")
            model.Add(start_idx <= 3).OnlyEnforceIf(start_le_3)
            model.Add(start_idx > 3).OnlyEnforceIf(start_le_3.Not())
            
            end_ge_4 = model.NewBoolVar(f"end_ge_4_{g}_{day}")
            model.Add(end_idx >= 4).OnlyEnforceIf(end_ge_4)
            model.Add(end_idx < 4).OnlyEnforceIf(end_ge_4.Not())
            
            crosses_lunch = model.NewBoolVar(f"crosses_lunch_{g}_{day}")
            model.AddMinEquality(crosses_lunch, [start_le_3, end_ge_4])
            
            windows = model.NewIntVar(0, 6, f"windows_{g}_{day}")
            model.Add(windows == end_idx - start_idx + 1 - total_classes - crosses_lunch).OnlyEnforceIf(day_active)
            model.Add(windows == 0).OnlyEnforceIf(day_active.Not())
            
            penalties.append(windows * 20) # Штраф за каждое окно

            # Обед (ЖЕСТКОЕ ПРАВИЛО: нельзя занимать и 3, и 4 пару)
            if len(hc_day) >= 4:
                model.AddBoolOr([hc_day[2].Not(), hc_day[3].Not()])

    # Синхронизация прогресса (Лекции должны опережать семинары)
    for subj, subj_data in subjects.items():
        if subj_data["lectures"] > 0 and subj_data["seminars"] > 0:
            total_lec = subj_data["lectures"]
            total_sem = subj_data["seminars"]
            
            base_g = STREAMS.get(subj, [GROUPS[0]])[0]
            
            cum_lec = 0
            for day in days:
                day_lecs = sum(x[(base_g, subj, "lec", s)] for s in SLOTS if s[0] == day)
                cum_lec += day_lecs
                
                for g in GROUPS:
                    if (g, subj, "sem", SLOTS[0]) not in x: continue
                    cum_sem = sum(x[(g, subj, "sem", s)] for s in SLOTS if s[0] <= day)
                    # Ожидаем, что пропорция прочитанных лекций >= пропорции семинаров
                    # cum_lec / total_lec >= cum_sem / total_sem => cum_lec * total_sem >= cum_sem * total_lec
                    viol = model.NewIntVar(-10000, 10000, f"viol_{subj}_{g}_{day}")
                    model.Add(viol == cum_sem * total_lec - cum_lec * total_sem)
                    
                    viol_pos = model.NewIntVar(0, 10000, f"viol_pos_{subj}_{g}_{day}")
                    model.AddMaxEquality(viol_pos, [0, viol])
                    penalties.append(viol_pos * 2)

    model.Minimize(sum(penalties))

    solver = cp_model.CpSolver()
    max_t = 320
    solver.parameters.log_search_progress = True
    solver.parameters.max_time_in_seconds = max_t
    solver.parameters.num_search_workers = 8
    
    print("⏳ Решаем Этап 1 (Время и Преподаватели)...")
    
    import sys, time, threading
    status = None
    
    def run_solver():
        nonlocal status
        status = solver.Solve(model)
        
    t = threading.Thread(target=run_solver)
    t.start()
    
    start_time = time.time()
    while t.is_alive():
        elapsed = int(time.time() - start_time)
        if elapsed > max_t:
            elapsed = max_t
            
        bar_len = 40
        filled_len = int(bar_len * elapsed / max_t)
        bar = '█' * filled_len + '-' * (bar_len - filled_len)
        sys.stdout.write(f'\r⏳ Вычисления: |{bar}| {elapsed}с / {max_t}с (таймаут)')
        sys.stdout.flush()
        time.sleep(0.5)
        
    sys.stdout.write('\r' + ' ' * 80 + '\r')
    sys.stdout.flush()

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("✅ Этап 1 завершен!")
        schedule = []
        for (g, subj, t, s), var in x.items():
            if solver.Value(var) == 1:
                schedule.append({"group": g, "subject": subj, "type": t, "slot": s})
                
        unassigned_warnings = []
        for (g, subj, t), (deficit_var, target) in unassigned_vars.items():
            val = solver.Value(deficit_var)
            if val > 0:
                msg = f"Не удалось выставить {val} из {target} пар ({t})"
                unassigned_warnings.append({"group": g, "subject": subj, "type": t, "msg": msg})
                
        return schedule, SLOTS, unassigned_warnings
    else:
        print("❌ Решение не найдено. Смягчите жесткие ограничения.")
        return None, SLOTS, []

# =========================
# ЭТАП 2: АУДИТОРИИ (Жадное + Ошибки)
# =========================
def assign_rooms(schedule, SLOTS):
    final_schedule = []
    warnings = [] # [ {"group", "subject", "slot", "msg"} ]

    # Группируем расписание по слотам
    by_slot = collections.defaultdict(list)
    for entry in schedule:
        by_slot[entry["slot"]].append(entry)

    print("⏳ Решаем Этап 2 (Аудитории)...")
    
    # Чтобы не дублировать лекции (они для всего потока в одной аудитории)
    for s in SLOTS:
        day_events = by_slot[s]
        if not day_events: continue
        
        # Склеиваем лекции потока в 1 событие
        events = [] # { subject, type, groups: [], size: 0 }
        
        # Сначала семинары
        for ev in day_events:
            if ev["type"] == "sem":
                size = GROUP_SIZES.get(ev["group"], 20)
                events.append({"subject": ev["subject"], "type": ev["type"], "groups": [ev["group"]], "size": size, "original": [ev]})
                
        # Затем лекции
        lec_events = [ev for ev in day_events if ev["type"] == "lec"]
        lec_grouped = collections.defaultdict(list)
        for ev in lec_events:
            lec_grouped[ev["subject"]].append(ev)
            
        for subj, evs in lec_grouped.items():
            size = sum(GROUP_SIZES.get(e["group"], 20) for e in evs)
            events.append({"subject": subj, "type": "lec", "groups": [e["group"] for e in evs], "size": size, "original": evs})
            
        # Сортируем события по размеру (крупные первыми)
        events.sort(key=lambda x: x["size"], reverse=True)
        
        available_rooms = set(ROOMS.keys())
        
        # Убираем недоступные в этот слот аудитории
        for r_name, r_data in ROOMS.items():
            if "room" in UNAVAILABLE_TIMES and r_name in UNAVAILABLE_TIMES["room"]:
                if (s[0].weekday(), s[1]) in UNAVAILABLE_TIMES["room"][r_name]:
                    available_rooms.discard(r_name)

        # Назначаем
        for ev in events:
            best_room = None
            best_score = -9999
            warning_msg = None
            
            target_type = "lec" if ev["type"] == "lec" else subjects[ev["subject"]].get("type_sem", "sem")
            
            for r in available_rooms:
                room_data = ROOMS[r]
                score = 0
                
                # Мягкое: тип аудитории совпадает
                type_match = (room_data["type"] == target_type)
                if type_match: score += 100
                
                # Мягкое: вместимость
                cap_diff = room_data["capacity"] - ev["size"]
                if cap_diff >= 0:
                    score += 50
                    score -= cap_diff # Чем ближе размер, тем лучше (меньше избыток)
                else:
                    score -= 500 # Не влезают!
                    
                if score > best_score:
                    best_score = score
                    best_room = r
                    
            if best_room:
                available_rooms.remove(best_room)
                room_data = ROOMS[best_room]
                
                # Проверяем мягкие нарушения
                if room_data["capacity"] < ev["size"]:
                    warning_msg = f"Вместимость: {room_data['capacity']} мест на {ev['size']} чел."
                elif room_data["type"] != target_type:
                    warning_msg = f"Тип: Аудитория {room_data['type']} для занятий {target_type}."
                
                for orig in ev["original"]:
                    cp = dict(orig)
                    cp["room"] = best_room
                    if warning_msg:
                        cp["warning"] = warning_msg
                        warnings.append({"date": s[0], "lesson": s[1], "group": cp["group"], "subject": cp["subject"], "msg": warning_msg})
                    final_schedule.append(cp)
            else:
                # Нет свободных аудиторий (Желтая/Красная ошибка)
                for orig in ev["original"]:
                    cp = dict(orig)
                    cp["room"] = "НЕТ АУДИТОРИИ"
                    cp["warning"] = "Не хватило свободных аудиторий!"
                    warnings.append({"date": s[0], "lesson": s[1], "group": cp["group"], "subject": cp["subject"], "msg": "Нет аудитории!"})
                    final_schedule.append(cp)

    print("✅ Этап 2 завершен!")
    return final_schedule, warnings

# =========================
# ЗАПУСК
# =========================
if __name__ == "__main__":
    schedule, SLOTS, unassigned_warnings = solve_time_schedule()
    if schedule is not None:
        final_schedule, warnings = assign_rooms(schedule, SLOTS)
        all_warnings = warnings + unassigned_warnings
        save(final_schedule, all_warnings, SLOTS)
