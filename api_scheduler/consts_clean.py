import datetime
import json
import os

# =========================
# ПАРАМЕТРЫ
# =========================

START = datetime.date(2025, 9, 1)
END = datetime.date(2025, 12, 28)

LESSONS = [1, 2, 3, 4, 5, 6]
STUDY_DAYS = [0, 1, 2, 3, 4, 5]

HOLIDAYS = {
    datetime.date(2025, 5, 1),
    datetime.date(2025, 5, 8),
    datetime.date(2025, 5, 9),
}

GROUPS = ["G1", "G2"]

GROUP_SIZES = {
    "G1": 25,
    "G2": 20,
}

ROOMS = {
    "101": {"capacity": 30, "type": "sem"},
    "102": {"capacity": 20, "type": "sem"},
    "103": {"capacity": 80, "type": "lec"},
    "104": {"capacity": 60, "type": "lec"},
    "105": {"capacity": 15, "type": "lab"},
    "106": {"capacity": 30, "type": "sem"},
    "Спортзал": {"capacity": 100, "type": "sem"} 
}

# =========================
# ЗАГРУЗКА ИЗ JSON
# =========================

def load_data():
    base_dir = os.path.dirname(__file__)
    
    with open(os.path.join(base_dir, 'output.json'), 'r', encoding='utf-8') as f:
        output_data = json.load(f)
    
    with open(os.path.join(base_dir, 'teachers.json'), 'r', encoding='utf-8') as f:
        teachers_data = json.load(f)

    subjects = {}
    UNAVAILABLE_TIMES = {"teacher": {}, "group": {}, "room": {}}

    wd_map = {
        "понедельник": 0,
        "вторник": 1,
        "среда": 2,
        "четверг": 3,
        "пятница": 4,
        "суббота": 5,
        "воскресенье": 6
    }
    
    # 1. Читаем преподавателей
    teacher_by_subj = {}
    for entry in teachers_data:
        teacher_name = entry.get("teacher", "").strip()
        subj_name = entry.get("subject", "").strip()
        
        if not teacher_name or not subj_name:
            continue
            
        # Берём только первого преподавателя (избегаем дублей по словам пользователя)
        if subj_name not in teacher_by_subj:
            teacher_by_subj[subj_name] = teacher_name
            
        schedule = entry.get("schedule", {})
        UNAVAILABLE_TIMES["teacher"][teacher_name] = []
        
        for day_name, slots in schedule.items():
            wd = wd_map.get(day_name.lower())
            if wd is None: continue
            
            if slots == "all":
                pass # доступен всегда в этот день
            elif isinstance(slots, list):
                if not slots:
                    for l in range(1, 7):
                        UNAVAILABLE_TIMES["teacher"][teacher_name].append((wd, l))
                else:
                    for l in range(1, 7):
                        if l not in slots:
                            UNAVAILABLE_TIMES["teacher"][teacher_name].append((wd, l))

    # 2. Выставляем предметы на основе output.json
    for raw_subj, data in output_data.items():
        subj_name = raw_subj.strip()
        
        # Ищем преподавателя по вхождению подстрок
        assigned_teacher = "Неизвестно"
        for t_subj, t_name in teacher_by_subj.items():
            if subj_name.lower() in t_subj.lower() or t_subj.lower() in subj_name.lower():
                assigned_teacher = t_name
                break
                
        lec = data.get("Лекции", 0) // 2
        sem = data.get("Семинары", 0) // 2
        lab = data.get("Лабораторные", 0) // 2
        
        total_sem = sem + lab
        type_sem = "lab" if lab > 0 else "sem"
        
        if lec > 0 or total_sem > 0:
            subjects[subj_name] = {
                "teacher": assigned_teacher,
                "lectures": lec,
                "seminars": total_sem,
                "type_sem": type_sem
            }

    return subjects, UNAVAILABLE_TIMES

subjects, UNAVAILABLE_TIMES = load_data()

# 3. Все лекции проводим потоком (для всех групп)
STREAMS = {
    subj: GROUPS for subj, data in subjects.items() if data["lectures"] > 0
}

FIXED_SCHEDULES = {
    "G1": [],
    "G2": []
}

def is_valid(teacher, slot):
    return True
