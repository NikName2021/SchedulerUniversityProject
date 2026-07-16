import asyncio
from typing import Any

from celery import Celery, chord
from core.config import REDIS_URL, engine
from services.scalable_generation_service import ScalableGenerationService
from services.scalable_scheduler import solve_event_component

celery_app = Celery("scheduler", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    broker_transport_options={"max_retries": 3},
    result_expires=3600,
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


def _run_async(coroutine: Any) -> Any:
    async def run_and_dispose() -> Any:
        try:
            return await coroutine
        finally:
            await engine.dispose()

    return asyncio.run(run_and_dispose())


@celery_app.task(name="scheduler.solve_component")
def solve_schedule_component_task(
    task_id: int,
    component_id: int,
    events: list[dict[str, Any]],
    context: dict[str, Any],
) -> dict[str, Any]:
    try:
        result = solve_event_component(events, context)
    except Exception as exc:
        result = {
            "status": "failed",
            "assignments": [],
            "unassigned": [],
            "error": str(exc),
            "metrics": {"events": len(events), "variables": 0, "constraints": 0},
        }
    _run_async(
        ScalableGenerationService.record_component_result(task_id, component_id, result)
    )
    return result


@celery_app.task(name="scheduler.finalize_schedule")
def finalize_schedule_task(
    component_results: list[dict[str, Any]],
    task_id: int,
    context: dict[str, Any],
) -> bool:
    return _run_async(
        ScalableGenerationService.finalize(task_id, component_results, context)
    )


@celery_app.task(name="scheduler.generate_schedule")
def generate_schedule_task(
    task_id: int,
    selected_groups: list[str],
    holidays: list[str],
    enabled_types: list[str],
    start_date: str | None,
    end_date: str | None,
    planning_week_id: int | None = None,
) -> dict[str, Any]:
    payload = _run_async(
        ScalableGenerationService.prepare(
            task_id,
            selected_groups,
            holidays,
            enabled_types,
            start_date,
            end_date,
            planning_week_id,
        )
    )
    if payload is None:
        return {"dispatched": 0, "task_id": task_id}

    context = payload["context"]
    signatures = [
        solve_schedule_component_task.s(
            task_id,
            component["component_id"],
            component["events"],
            context,
        )
        for component in payload["components"]
    ]
    try:
        workflow = chord(signatures)(finalize_schedule_task.s(task_id, context))
    except Exception as exc:
        _run_async(
            ScalableGenerationService.fail(
                task_id, f"Failed to dispatch component workflow: {exc}"
            )
        )
        raise
    _run_async(ScalableGenerationService.save_workflow_id(task_id, workflow.id))
    return {
        "dispatched": len(signatures),
        "task_id": task_id,
        "workflow_id": workflow.id,
    }
