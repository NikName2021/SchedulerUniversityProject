import datetime

# =========================
# ПАРАМЕТРЫ
# =========================

START = datetime.date(2025, 2, 10)
END = datetime.date(2025, 6, 8)

LESSONS = [1, 2, 3, 4, 5, 6]

# Дни недели, когда можно ставить пары (0 - Пн, 1 - Вт, ... 6 - Вс)
STUDY_DAYS = [3, 4]

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

# Потоки для лекций. Предмет -> список групп
STREAMS = {
    "География": ["G1", "G2"],
    "Литература": ["G1", "G2"],
    "Русский": ["G1", "G2"],
    "ОБЖ": ["G1", "G2"],
    "История": ["G1", "G2"],
    "Общество": ["G1", "G2"],
    "Физра": ["G1", "G2"],
}

# Аудитории (вместимость и тип)
ROOMS = {
    "101": {"capacity": 30, "type": "sem"},
    "102": {"capacity": 20, "type": "sem"},
    "103": {"capacity": 80, "type": "lec"},
    "104": {"capacity": 60, "type": "lec"},
    "105": {"capacity": 15, "type": "lab"},
    "106": {"capacity": 30, "type": "sem"},
    "Спортзал": {"capacity": 100, "type": "sem"} 
}

# Заблокированное время (жесткое)
UNAVAILABLE_TIMES = {
    "teacher": {
        "vaganov": [(0, 1), (0, 2)], # Пн, 1-2 пара (пример)
    },
    "group": {
        "G1": [(3, 6)], # Ср, 6 пара (пример)
    },
    "room": {
        "103": [(4, 1)] 
    }
}

# Фиксации (жесткие) - словарь dict[group] -> list of dicts
FIXED_SCHEDULES = {
    "G1": [
        # {"date": datetime.date(2025, 2, 13), "lesson": 1, "subject": "История", "type": "lec"}
    ]
}

# =========================
# ПРЕДМЕТЫ
# =========================
# Добавлен параметр type_sem для лабораторок и тд
subjects = {
    "География": {"teacher": "vaganov", "lectures": 8, "seminars": 8, "type_sem": "sem"},
    "Литература": {"teacher": "bahtina", "lectures": 8, "seminars": 18, "type_sem": "sem"},
    "Русский": {"teacher": "myak", "lectures": 4, "seminars": 7, "type_sem": "sem"},
    "ОБЖ": {"teacher": "nugaev", "lectures": 10, "seminars": 5, "type_sem": "sem"},
    "История": {"teacher": "kolobov", "lectures": 8, "seminars": 7, "type_sem": "sem"},
    "Общество": {"teacher": "sova", "lectures": 9, "seminars": 6, "type_sem": "sem"},
    "Физра": {"teacher": "sagd", "lectures": 13, "seminars": 0, "type_sem": "sem"},
    "Английский": {"teacher": "4 щлишр", "lectures": 0, "seminars": 28, "type_sem": "sem"},
}

# =========================
# ДОСТУПНОСТЬ (СТАРАЯ ЛОГИКА)
# =========================
def is_valid(teacher, slot):
    d, lesson = slot
    wd = d.weekday()

    if teacher == "vaganov":
        return wd == 4 and lesson in [1, 2]
    if teacher == "bahtina":
        return wd == 3
    if teacher == "myak":
        return (wd == 3 and lesson == 1) or (wd == 4 and lesson == 4)
    if teacher == "nugaev":
        return lesson in [4, 5]
    if teacher == "kolobov":
        if wd == 3:
            return lesson in [2, 3, 5]
        if wd == 4:
            return lesson in [2, 3, 4]
    if teacher == "sova":
        return wd == 3 and lesson in [1, 2, 3, 5]
    if teacher == "sagd":
        return wd == 4 and lesson == 4

    return True
