import argparse
import json
import os
import secrets
import string
from pathlib import Path

DEFAULT_USERS_PATH = Path("secrets/default_users.json")


def random_word(length: int) -> str:
    return "".join(secrets.choice(string.ascii_letters) for _ in range(length))


def random_password(length: int = 24) -> str:
    if length < 12:
        raise ValueError("Password length must be at least 12 characters")
    required = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#%_-"),
    ]
    alphabet = string.ascii_letters + string.digits + "!@#%_-"
    password = required + [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def ensure_default_users_file(path: Path = DEFAULT_USERS_PATH) -> bool:
    if path.exists():
        print(f"[config] keeping existing user secret: {path}")
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "users": [
            {
                "username": "admin",
                "password": random_password(),
                "display_name": "Администратор",
                "role": "admin",
            },
            {
                "username": "operator",
                "password": random_password(),
                "display_name": "Оператор расписания",
                "role": "operator",
            },
        ],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)
    print(f"[config] generated default user credentials: {path}")
    print("[config] keep this file private and change the passwords after first login")
    return True


def write_environment_file(path: Path = Path(".env")) -> None:
    path.write_text(
        f"""POSTGRES_USER=user_{random_word(10)}
POSTGRES_PASSWORD={random_word(25)}
POSTGRES_DATABASE={random_word(10)}
POSTGRES_PORT=5446

CORS_ORIGINS=http://localhost,http://localhost:5173
ALLOWED_HOSTS=localhost,127.0.0.1
MAX_UPLOAD_BYTES=10485760
MAX_CALCULATION_PACKAGE_BYTES=52428800
SERVER_SOLVER_ENABLED=false
AUTH_COOKIE_NAME=scheduler_session
AUTH_COOKIE_SECURE=false
AUTH_SESSION_HOURS=8
AUTH_MAX_SESSIONS_PER_USER=5
AUTH_MAX_FAILED_LOGINS=5
AUTH_LOCKOUT_MINUTES=15
DEFAULT_USERS_FILE=./secrets/default_users.json
CELERY_WORKER_CONCURRENCY=2
NGINX_FILE=local_nginx.conf
""",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)
    print(f"[config] generated environment file: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate local deployment secrets")
    parser.add_argument(
        "--users-only",
        action="store_true",
        help="Create only secrets/default_users.json without replacing .env",
    )
    args = parser.parse_args()

    if not args.users_only:
        write_environment_file()
    ensure_default_users_file()


if __name__ == "__main__":
    main()
