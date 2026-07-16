import asyncio
from typing import Any

from celery import Celery
from core.config import REDIS_URL
from services.generation_service import GenerationService

celery_app = Celery("scheduler", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    broker_transport_options={"max_retries": 3},
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_serializer="json",
    task_soft_time_limit=840,
    task_time_limit=900,
    task_track_started=True,
    timezone="Europe/Moscow",
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="scheduler.generate_schedule")
def generate_schedule_task(
    task_id: int,
    selected_groups: list[str],
    holidays: list[str],
    enabled_types: list[str],
    start_date: str | None,
    end_date: str | None,
) -> bool | None:
    """Run the CPU-bound scheduler outside the API process."""
    result: Any = asyncio.run(
        GenerationService.run_generation(
            task_id,
            selected_groups,
            holidays,
            enabled_types,
            start_date,
            end_date,
        )
    )
    return result
