from datetime import date

# Generation Settings
MAX_TIME_SECONDS = 100
NUM_WORKERS = 8
LOGGING_ENABLED = True

# Scheduling Defaults
DEFAULT_START_DATE = date(2025, 9, 1)
DEFAULT_END_DATE = date(2025, 9, 7)
STUDY_DAYS = [0, 1, 2, 3, 4, 5]  # 0=Mon, 5=Sat
LESSONS = [1, 2, 3, 4, 5, 6, 7]

# Rooms Configuration
ROOMS = {
    "101": {"capacity": 30, "type": "sem"},
    "102": {"capacity": 20, "type": "sem"},
    "103": {"capacity": 80, "type": "lec"},
    "104": {"capacity": 60, "type": "lec"},
    "105": {"capacity": 15, "type": "lab"},
    "106": {"capacity": 30, "type": "sem"},
    "201": {"capacity": 100, "type": "lec"},
    "202": {"capacity": 40, "type": "sem"},
}

# Penalties and Weights
PENALTY_UNASSIGNED = 100000
PENALTY_LATE_LESSON = 3  # Multiplied by lesson index
PENALTY_SATURDAY = 60
PENALTY_WINDOW = 20  # Per gap between lessons
PENALTY_SYNC_STREAM = 10  # Per lesson difference between groups in stream
PENALTY_PROGRESS_VIOLATION = 2  # When seminar happens before corresponding lecture
PENALTY_MORNING_PRIORITY = 30  # Penalty per hour late for high-priority subjects
