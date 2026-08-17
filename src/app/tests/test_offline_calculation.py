import copy
import datetime

import pytest
import services.scalable_generation_service as scalable_module
from database import (
    FileType,
    GenerationTask,
    ImportBatch,
    OfflineCalculation,
    ScheduleEntry,
    Stream,
    StreamGroup,
    Teacher,
)
from offline_solver import solve_task_jobs
from services.calculation_package import (
    PackageValidationError,
    create_result_archive,
    read_task_archive,
)
from services.offline_calculation_service import (
    OfflineCalculationService,
    OfflineTaskSpec,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker


@pytest.mark.asyncio
async def test_offline_calculation_round_trip(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_sessionmaker = sessionmaker(
        db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    monkeypatch.setattr(scalable_module, "sessionmaker", test_sessionmaker)

    batch = ImportBatch(filename="streams.xlsx", file_type=FileType.STREAMS)
    teacher = Teacher(name="Иванов И.И.")
    db_session.add_all([batch, teacher])
    await db_session.flush()
    stream = Stream(
        import_batch_id=batch.id,
        teacher_id=teacher.id,
        event_name="Математика",
        stream_type="Лекция",
        lessons_count=1,
    )
    db_session.add(stream)
    await db_session.flush()
    db_session.add(StreamGroup(stream_id=stream.id, group_name="А-01", group_size=20))
    await db_session.commit()

    package, task_ids = await OfflineCalculationService.create_task_package(
        [
            OfflineTaskSpec(
                groups=["А-01"],
                holidays=[],
                settings={"enabled_types": ["Лекция"]},
                planning_week_id=None,
                start_date=datetime.datetime(2026, 9, 7),
                end_date=datetime.datetime(2026, 9, 7),
            ),
            OfflineTaskSpec(
                groups=["А-01"],
                holidays=[],
                settings={"enabled_types": ["Лекция"]},
                planning_week_id=None,
                start_date=datetime.datetime(2026, 9, 8),
                end_date=datetime.datetime(2026, 9, 8),
            ),
        ],
        db_session,
    )
    assert len(task_ids) == 2
    for task_id in task_ids:
        task = await db_session.get(GenerationTask, task_id)
        assert task is not None
        assert task.status == "awaiting_result"

    _manifest, task_jobs = read_task_archive(package.getvalue())
    result_jobs = solve_task_jobs(task_jobs, component_workers=1, solver_workers=1)
    tampered_jobs = copy.deepcopy(result_jobs)
    tampered_jobs[0]["component_results"][0]["result"]["assignments"][0]["slot"] = [
        "2030-01-01",
        1,
    ]
    with pytest.raises(PackageValidationError, match="outside the task horizon"):
        await OfflineCalculationService.import_result_package(
            create_result_archive(tampered_jobs).getvalue(), db_session
        )
    result_package = create_result_archive(result_jobs)

    def fail_if_server_room_solver_runs(*_args, **_kwargs):
        raise AssertionError("room solver must run on the laptop")

    monkeypatch.setattr(
        scalable_module, "assign_rooms_matching", fail_if_server_room_solver_runs
    )

    imported = await OfflineCalculationService.import_result_package(
        result_package.getvalue(), db_session
    )

    db_session.expire_all()
    entries = list(
        (
            await db_session.execute(
                select(ScheduleEntry).where(ScheduleEntry.task_id.in_(task_ids))
            )
        ).scalars()
    )
    records = list(
        (
            await db_session.execute(
                select(OfflineCalculation).where(
                    OfflineCalculation.task_id.in_(task_ids)
                )
            )
        ).scalars()
    )
    assert imported == [
        {"task_id": task_id, "status": "success", "accepted": True}
        for task_id in task_ids
    ]
    for task_id in task_ids:
        task = await db_session.get(GenerationTask, task_id)
        assert task is not None and task.status == "success"
    assert len(entries) == 2
    assert {entry.group_name for entry in entries} == {"А-01"}
    assert len(records) == 2
    assert all(record.result_payload_json for record in records)


@pytest.mark.asyncio
async def test_offline_result_must_match_exported_snapshot(
    db_session: AsyncSession,
) -> None:
    task = GenerationTask(
        groups_json="[]",
        holidays_json="[]",
        settings_json="{}",
        status="awaiting_result",
    )
    db_session.add(task)
    await db_session.flush()
    record = OfflineCalculation(
        task_id=task.id,
        job_uuid="1b96ad85-55f7-4b06-8834-16d256237f86",
        input_sha256="a" * 64,
        input_payload_json=(
            '{"components":[],"context":{},'
            '"job_uuid":"1b96ad85-55f7-4b06-8834-16d256237f86"}'
        ),
    )
    db_session.add(record)
    await db_session.commit()
    result = create_result_archive(
        [
            {
                "job_uuid": record.job_uuid,
                "input_sha256": "b" * 64,
                "component_results": [],
                "room_assignments": [],
            }
        ]
    )

    with pytest.raises(PackageValidationError, match="different task snapshot"):
        await OfflineCalculationService.import_result_package(
            result.getvalue(), db_session
        )
