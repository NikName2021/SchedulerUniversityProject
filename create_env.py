import random
import string


def random_word(length: int) -> str:
    letters = string.ascii_letters
    return "".join(random.choice(letters) for _ in range(length))


with open(".env", "w", encoding="utf-8") as f:
    f.write(
        f"""
POSTGRES_USER=user_{random_word(10)}
POSTGRES_PASSWORD={random_word(25)}
POSTGRES_DATABASE={random_word(10)}
POSTGRES_PORT=5446

CORS_ORIGINS=http://localhost,http://localhost:5173
ALLOWED_HOSTS=localhost,127.0.0.1
MAX_UPLOAD_BYTES=10485760
CELERY_WORKER_CONCURRENCY=2
NGINX_FILE=local_nginx.conf

"""
    )
