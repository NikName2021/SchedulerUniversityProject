from datetime import date

# Generation Settings
NUM_WORKERS = 8
MAX_GENERATION_HORIZON_DAYS = 14
MAX_ESTIMATED_DECISION_VARIABLES = 100_000
LOGGING_ENABLED = True

# Authentication
AUTH_COOKIE_NAME = "scheduler_session"
AUTH_COOKIE_SECURE = False
AUTH_SESSION_HOURS = 8
AUTH_MAX_SESSIONS_PER_USER = 5
AUTH_MAX_FAILED_LOGINS = 5
AUTH_LOCKOUT_MINUTES = 15

# Scheduling Defaults
DEFAULT_START_DATE = date(2025, 9, 1)
DEFAULT_END_DATE = date(2025, 9, 7)
STUDY_DAYS = [0, 1, 2, 3, 4, 5]  # 0=Mon, 5=Sat
ALL_LESSONS = [1, 2, 3, 4, 5, 6, 7]

# Rooms Configuration
ROOM_ASSIGNMENT_ENABLED = False
ROOM_FUND_ENABLED = False

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
