import asyncio
from collections.abc import Coroutine
from typing import Any

from celery import Celery, chord
from celery.signals import worker_process_init, worker_process_shutdown
from core.config import REDIS_URL, engine, sessionmaker
from database.workspace import bind_task_workspace
from services.generation_lifecycle_service import GenerationLifecycleService
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
    task_reject_on_worker_lost=False,
    task_serializer="json",
    task_soft_time_limit=840,
    task_time_limit=900,
    task_track_started=True,
    timezone="Europe/Moscow",
    worker_prefetch_multiplier=1,
)


_worker_loop: asyncio.AbstractEventLoop | None = None


@worker_process_init.connect
def _init_worker_process(**_kwargs: Any) -> None:
    global _worker_loop
    # A prefork child must never reuse connections opened by its parent.
    engine.sync_engine.dispose(close=False)
    _worker_loop = asyncio.new_event_loop()


@worker_process_shutdown.connect
def _shutdown_worker_process(**_kwargs: Any) -> None:
    global _worker_loop
    if _worker_loop is None:
        return
    try:
        _worker_loop.run_until_complete(engine.dispose())
    finally:
        _worker_loop.close()
        _worker_loop = None


def _run_async(coroutine: Coroutine[Any, Any, Any]) -> Any:
    global _worker_loop
    if _worker_loop is None:
        _worker_loop = asyncio.new_event_loop()
    task = _worker_loop.create_task(coroutine)
    try:
        return _worker_loop.run_until_complete(task)
    finally:
        # Celery's soft timeout can interrupt run_until_complete directly.
        if not task.done():
            task.cancel()
            _worker_loop.run_until_complete(
                asyncio.gather(task, return_exceptions=True)
            )


@celery_app.task(name="scheduler.solve_component")
def solve_schedule_component_task(
    task_id: int,
    component_id: int,
    events: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if context is None:
        context = _run_async(
            ScalableGenerationService.load_solver_context(task_id, component_id)
        )
    if context is None:
        return {"status": "skipped"}
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
    context: dict[str, Any] | None = None,
) -> bool:
    try:
        if context is None:
            context = _run_async(ScalableGenerationService.load_solver_context(task_id))
        if context is None:
            return False
        return _run_async(
            ScalableGenerationService.finalize(task_id, component_results, context)
        )
    except Exception as exc:
        _run_async(
            ScalableGenerationService.fail(
                task_id, f"Failed to finalize schedule: {exc}"
            )
        )
        raise


@celery_app.task(name="scheduler.handle_workflow_error")
def handle_workflow_error_task(task_id: int) -> None:
    _run_async(
        _mark_workflow_failed(
            task_id,
            "Solver worker was lost or a Celery component terminated unexpectedly",
        )
    )


async def _mark_workflow_failed(task_id: int, message: str) -> None:
    async with sessionmaker() as session:
        await bind_task_workspace(session, task_id)
        await GenerationLifecycleService.fail_active_task(task_id, message, session)


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
    try:
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
    except Exception as exc:
        _run_async(
            ScalableGenerationService.fail(
                task_id, f"Failed to prepare generation: {exc}"
            )
        )
        raise
    if payload is None:
        return {"dispatched": 0, "task_id": task_id}

    signatures = [
        solve_schedule_component_task.s(
            task_id,
            component["component_id"],
            component["events"],
        )
        for component in payload["components"]
    ]
    try:
        callback = finalize_schedule_task.s(task_id).on_error(
            handle_workflow_error_task.si(task_id)
        )
        workflow = chord(signatures)(callback)
    except Exception as exc:
        _run_async(
            ScalableGenerationService.fail(
                task_id, f"Failed to dispatch component workflow: {exc}"
            )
        )
        raise
    component_ids = [
        result.id for result in (workflow.parent.results if workflow.parent else [])
    ]
    _run_async(
        ScalableGenerationService.save_workflow_id(task_id, workflow.id, component_ids)
    )
    return {
        "dispatched": len(signatures),
        "task_id": task_id,
        "workflow_id": workflow.id,
    }
