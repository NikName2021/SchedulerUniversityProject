from __future__ import annotations

import datetime
import json
from typing import Any

from database import GenerationIssue, GenerationLock, GenerationTask
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

TERMINAL_STATUSES = {"success", "partial", "failed", "canceled"}
ACTIVE_STATUSES = {"queued", "running"}


class GenerationLifecycleService:
    @staticmethod
    def scope_keys(
        groups: list[str],
        planning_week_id: int | None,
        start_date: datetime.datetime | None,
        end_date: datetime.datetime | None,
    ) -> list[str]:
        if planning_week_id is not None:
            period = f"week:{planning_week_id}"
        else:
            start = start_date.date().isoformat() if start_date else "default"
            end = end_date.date().isoformat() if end_date else "default"
            period = f"range:{start}:{end}"
        return [f"{period}:group:{group}" for group in sorted(set(groups))]

    @classmethod
    async def reserve_task(
        cls,
        db: AsyncSession,
        *,
        groups: list[str],
        holidays: list[str],
        settings: dict[str, Any],
        planning_week_id: int | None,
        start_date: datetime.datetime | None,
        end_date: datetime.datetime | None,
        parent_task_id: int | None = None,
        semester_batch_id: str | None = None,
    ) -> GenerationTask:
        await db.execute(
            delete(GenerationLock).where(
                GenerationLock.task_id.in_(
                    select(GenerationTask.id).where(
                        GenerationTask.status.in_(TERMINAL_STATUSES)
                    )
                )
            )
        )
        keys = cls.scope_keys(groups, planning_week_id, start_date, end_date)
        conflict = await db.scalar(
            select(GenerationLock.scope_key).where(GenerationLock.scope_key.in_(keys))
        )
        if conflict:
            raise RuntimeError(f"Generation is already running for {conflict}")

        version_query = select(func.max(GenerationTask.version_number))
        if planning_week_id is not None:
            version_query = version_query.where(
                GenerationTask.planning_week_id == planning_week_id
            )
        else:
            version_query = version_query.where(
                GenerationTask.planning_week_id.is_(None),
                GenerationTask.start_date == start_date,
                GenerationTask.end_date == end_date,
            )
        version_number = int(await db.scalar(version_query) or 0) + 1
        task = GenerationTask(
            groups_json=json.dumps(groups),
            holidays_json=json.dumps(holidays),
            settings_json=json.dumps(settings),
            planning_week_id=planning_week_id,
            start_date=start_date,
            end_date=end_date,
            parent_task_id=parent_task_id,
            semester_batch_id=semester_batch_id,
            version_number=version_number,
            publication_status="draft",
            status="queued",
        )
        db.add(task)
        await db.flush()
        db.add_all([GenerationLock(scope_key=key, task_id=task.id) for key in keys])
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def release_locks(task_id: int, db: AsyncSession) -> None:
        await db.execute(
            delete(GenerationLock).where(GenerationLock.task_id == task_id)
        )

    @staticmethod
    async def publish(task: GenerationTask, db: AsyncSession) -> None:
        if task.status not in {"success", "partial"}:
            raise ValueError("Only a completed schedule can be published")
        if task.planning_week_id is not None:
            scope = GenerationTask.planning_week_id == task.planning_week_id
        else:
            scope = (
                GenerationTask.planning_week_id.is_(None)
                & (GenerationTask.start_date == task.start_date)
                & (GenerationTask.end_date == task.end_date)
            )
        await db.execute(
            update(GenerationTask)
            .where(
                scope,
                GenerationTask.id != task.id,
                GenerationTask.publication_status == "published",
            )
            .values(publication_status="archived")
        )
        task.publication_status = "published"
        task.published_at = datetime.datetime.utcnow()
        await db.commit()

    @staticmethod
    async def archive(task: GenerationTask, db: AsyncSession) -> None:
        if task.status in ACTIVE_STATUSES:
            raise ValueError("An active generation cannot be archived")
        task.publication_status = "archived"
        await db.commit()

    @staticmethod
    async def diagnostics(task_id: int, db: AsyncSession) -> dict[str, Any]:
        result = await db.execute(
            select(GenerationIssue)
            .where(GenerationIssue.task_id == task_id)
            .order_by(GenerationIssue.severity.desc(), GenerationIssue.id)
        )
        issues = list(result.scalars())
        counts_result = await db.execute(
            select(GenerationIssue.kind, func.count(GenerationIssue.id))
            .where(GenerationIssue.task_id == task_id)
            .group_by(GenerationIssue.kind)
        )
        return {
            "task_id": task_id,
            "counts": {kind: count for kind, count in counts_result},
            "issues": [
                {
                    "id": issue.id,
                    "kind": issue.kind,
                    "severity": issue.severity,
                    "message": issue.message,
                    "stream_id": issue.stream_id,
                    "group_name": issue.group_name,
                    "date": issue.date.isoformat() if issue.date else None,
                    "lesson_number": issue.lesson_number,
                    "details": (
                        json.loads(issue.details_json) if issue.details_json else {}
                    ),
                }
                for issue in issues
            ],
        }

    @classmethod
    async def fail_active_task(
        cls, task_id: int, message: str, db: AsyncSession
    ) -> None:
        task = await db.get(GenerationTask, task_id)
        if task is None or task.status not in ACTIVE_STATUSES:
            return
        task.status = "failed"
        task.progress_percent = 100
        task.error_message = message
        db.add(
            GenerationIssue(
                task_id=task_id,
                kind="worker",
                severity="error",
                message=message,
            )
        )
        await cls.release_locks(task_id, db)
        await db.commit()
