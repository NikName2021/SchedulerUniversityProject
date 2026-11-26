import datetime
import json
from types import SimpleNamespace

import pytest
from api.routes import scheduler
from database import (
    FileType,
    GenerationTask,
    ImportBatch,
    Stream,
    StreamGroup,
    SubjectScheduleRule,
    Teacher,
    WeeklyLessonDemand,
)
from schemas.planning import AcademicPeriodCreate
from services.planning_service import PlanningService
from services.scalable_scheduler import solve_event_component
from sqlalchemy import select


@pytest.fixture
async def subject_data(db_session):
    batch = ImportBatch(filename="rules.xlsx", file_type=FileType.STREAMS)
    teacher = Teacher(
        name="Преподаватель",
        restrictions_json=json.dumps(
            {
                "mode": "blacklist",
                "recurring": [f"4-{lesson}" for lesson in range(1, 8)],
                "specific": [],
            }
        ),
    )
    db_session.add_all([batch, teacher])
    await db_session.flush()
    streams = []
    for kind, count in [("Лекция", 2), ("Семинар", 4)]:
        stream = Stream(
            import_batch_id=batch.id,
            teacher_id=teacher.id,
            event_name="Математика",
            stream_type=kind,
            lessons_count=count,
        )
        db_session.add(stream)
        await db_session.flush()
        db_session.add(StreamGroup(stream_id=stream.id, group_name="A", group_size=20))
        streams.append(stream)
    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Период",
            starts_on=datetime.date(2026, 11, 16),
            ends_on=datetime.date(2026, 11, 29),
        ),
        db_session,
    )
    await db_session.commit()
    return teacher, streams, period


def request_for(period, *, hard=True, days=None, seminars=2):
    return {
        "subject": "Математика",
        "groups": ["A"],
        "start_date": "2026-11-16",
        "end_date": "2026-11-29",
        "week_ids": [week.id for week in period.weeks],
        "enabled_types": ["Лекция", "Семинар"],
        "rule": {
            "lectures": 1,
            "seminars": seminars,
            "laboratories": 0,
            "days_per_week": 2,
            "weekdays": days if days is not None else [0, 3],
            "days_hard": hard,
            "lecture_before_practice": True,
            "time_preference": "morning",
        },
    }


async def test_hard_availability_conflict_blocks_save(
    api_client, db_session, subject_data
):
    _, _, period = subject_data
    payload = request_for(period)
    response = await api_client.post(
        "/api/v1/scheduler/subject-rules/check", json=payload
    )
    assert response.status_code == 200
    assert response.json()["can_save"] is False
    assert "19.11 преподаватель недоступен" in response.json()["errors"][0]
    saved = await api_client.put("/api/v1/scheduler/subject-rules", json=payload)
    assert saved.status_code == 422
    assert not list((await db_session.execute(select(SubjectScheduleRule))).scalars())
    assert not list((await db_session.execute(select(WeeklyLessonDemand))).scalars())


async def test_soft_days_use_real_availability_and_persist(
    api_client, db_session, subject_data
):
    _, streams, period = subject_data
    payload = request_for(period, hard=False)
    response = await api_client.put("/api/v1/scheduler/subject-rules", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["can_save"] is True
    assert result["warnings"]
    assert all(
        datetime.date.fromisoformat(item["date"]).weekday() != 3
        for item in result["preview"]
    )
    records = list((await db_session.execute(select(SubjectScheduleRule))).scalars())
    assert len(records) == 1
    demands = list((await db_session.execute(select(WeeklyLessonDemand))).scalars())
    assert sorted(demand.lessons_count for demand in demands) == [1, 1, 2, 2]
    context = {
        key: value for key, value in payload.items() if key not in {"subject", "rule"}
    }
    loaded = await api_client.post(
        "/api/v1/scheduler/subject-rules/query", json=context
    )
    assert loaded.json()["items"][0]["saved"] is True
    assert loaded.json()["items"][0]["rule"]["seminars"] == 2
    assert {demand.stream_id for demand in demands} == {stream.id for stream in streams}


async def test_template_cannot_exceed_semester_workload(api_client, subject_data):
    _, _, period = subject_data
    response = await api_client.post(
        "/api/v1/scheduler/subject-rules/check",
        json=request_for(period, hard=False, seminars=3),
    )
    assert response.status_code == 200
    assert not response.json()["can_save"]
    assert "учебный план" in response.json()["errors"][0]


async def test_single_week_scope_and_schema_validation(api_client, subject_data):
    _, _, period = subject_data
    payload = request_for(period, days=[0, 2])
    payload["end_date"] = "2026-11-22"
    payload["week_ids"] = [period.weeks[0].id]
    response = await api_client.put("/api/v1/scheduler/subject-rules", json=payload)
    assert response.status_code == 200, response.text
    payload["rule"]["weekdays"] = [6]
    assert (
        await api_client.put("/api/v1/scheduler/subject-rules", json=payload)
    ).status_code == 422
    payload["rule"]["weekdays"] = [0, 2]
    payload["rule"]["days_per_week"] = 4
    assert (
        await api_client.put("/api/v1/scheduler/subject-rules", json=payload)
    ).status_code == 422


def test_solver_honors_days_composition_and_lecture_order():
    config = {
        "lectures": 1,
        "seminars": 2,
        "laboratories": 0,
        "days_per_week": 2,
        "weekdays": [0, 3],
        "days_hard": True,
        "lecture_before_practice": True,
        "time_preference": "morning",
    }
    context = {
        "start_date": "2026-11-16",
        "end_date": "2026-11-21",
        "holidays": [],
        "study_days": list(range(6)),
        "lessons": [1, 2, 3],
        "max_time_seconds": 2,
        "num_workers": 1,
        "require_full_placement": True,
        "subject_rules": [{"subject": "Математика", "group_name": "A", "rule": config}],
    }
    events = [
        {
            "id": str(i),
            "stream_id": i,
            "subject": "Математика",
            "groups": ["A"],
            "teacher": "T",
            "type": kind,
            "lessons_count": count,
            "priority": 5,
        }
        for i, kind, count in [(1, "lec", 1), (2, "sem", 2)]
    ]
    result = solve_event_component(events, context)
    assert result["status"] == "success"
    assert not result["unassigned"]
    assert len(result["assignments"]) == 3
    assert {
        datetime.date.fromisoformat(item["slot"][0]).weekday()
        for item in result["assignments"]
    } == {0, 3}
    lecture = next(item for item in result["assignments"] if item["type"] == "lec")
    assert all(
        item["slot"] > lecture["slot"]
        for item in result["assignments"]
        if item["type"] == "sem"
    )


async def test_saved_semester_rule_survives_redistribution_and_reaches_generator(
    api_client, db_session, subject_data, monkeypatch
):
    _, streams, period = subject_data
    week = period.weeks[0]
    payload = request_for(period, days=[0, 2])
    payload.update(end_date=week.ends_on.isoformat(), week_ids=[week.id])
    response = await api_client.put("/api/v1/scheduler/subject-rules", json=payload)
    assert response.status_code == 200, response.text

    await PlanningService.distribute_semester_demands(
        period.id, ["A"], ["Лекция", "Семинар"], set(), db_session
    )
    monkeypatch.setattr(
        scheduler.generate_schedule_task,
        "delay",
        lambda *args: SimpleNamespace(id="demo"),
    )
    response = await api_client.post(
        "/api/v1/scheduler/generate",
        json={
            "groups": ["A"],
            "planning_week_id": week.id,
            "settings": {"enabled_types": ["Лекция", "Семинар"]},
        },
    )
    assert response.status_code == 200, response.text
    task = await db_session.get(GenerationTask, response.json()["task_id"])
    settings = json.loads(task.settings_json)
    assert settings["subject_rules"] == [
        {"subject": "Математика", "group_name": "A", "rule": payload["rule"]}
    ]
    assert settings["subject_rule_counts"] == {
        str(streams[0].id): 1,
        str(streams[1].id): 2,
    }
    other_week = period.weeks[1]
    response = await api_client.post(
        "/api/v1/scheduler/generate",
        json={
            "groups": ["A"],
            "planning_week_id": other_week.id,
        },
    )
    assert response.status_code == 200, response.text
    other_task = await db_session.get(GenerationTask, response.json()["task_id"])
    assert "subject_rules" not in json.loads(other_task.settings_json)


async def test_other_workspace_cannot_reference_planning_week(
    unauthenticated_api_client, subject_data
):
    _, _, period = subject_data
    response = await unauthenticated_api_client.post(
        "/api/v1/scheduler/subject-rules/query",
        json={
            key: value
            for key, value in request_for(period).items()
            if key not in {"subject", "rule"}
        },
    )
    assert response.status_code == 401


async def test_subject_rule_supports_subgroup_labs_with_base_lectures_and_seminars(
    api_client, db_session, monkeypatch
):
    batch = ImportBatch(filename="biology.xlsx", file_type=FileType.STREAMS)
    teacher = Teacher(name="Минияров Ф.Т.")
    db_session.add_all([batch, teacher])
    await db_session.flush()

    lecture = Stream(
        import_batch_id=batch.id,
        teacher_id=teacher.id,
        event_name="Биология",
        stream_type="Лекция",
        lessons_count=5,
    )
    db_session.add(lecture)
    await db_session.flush()
    db_session.add_all(
        [
            StreamGroup(stream_id=lecture.id, group_name="ИОП-ИТ-25/1", group_size=22),
            StreamGroup(stream_id=lecture.id, group_name="ИОП-ИТ-25/2", group_size=23),
        ]
    )

    for group_name in ("ИОП-ИТ-25/1", "ИОП-ИТ-25/2"):
        seminar = Stream(
            import_batch_id=batch.id,
            teacher_id=teacher.id,
            event_name="Биология",
            stream_type="Семинар",
            lessons_count=3,
        )
        db_session.add(seminar)
        await db_session.flush()
        db_session.add(
            StreamGroup(stream_id=seminar.id, group_name=group_name, group_size=22)
        )
        for subgroup in ("L1", "L2"):
            lab = Stream(
                import_batch_id=batch.id,
                teacher_id=teacher.id,
                event_name="Биология",
                stream_type="Лабораторная",
                lessons_count=3,
            )
            db_session.add(lab)
            await db_session.flush()
            db_session.add(
                StreamGroup(
                    stream_id=lab.id,
                    group_name=f"{group_name} ({subgroup})",
                    group_size=11,
                )
            )

    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Семестр",
            starts_on=datetime.date(2026, 9, 7),
            ends_on=datetime.date(2026, 9, 27),
        ),
        db_session,
    )
    await db_session.commit()

    all_groups = [
        "ИОП-ИТ-25/1",
        "ИОП-ИТ-25/1 (L1)",
        "ИОП-ИТ-25/1 (L2)",
        "ИОП-ИТ-25/2",
        "ИОП-ИТ-25/2 (L1)",
        "ИОП-ИТ-25/2 (L2)",
    ]
    await PlanningService.distribute_semester_demands(
        period.id,
        all_groups,
        ["Лекция", "Семинар", "Лабораторная"],
        set(),
        db_session,
    )

    week = period.weeks[0]
    payload = {
        "subject": "Биология",
        "groups": all_groups,
        "start_date": week.starts_on.isoformat(),
        "end_date": week.ends_on.isoformat(),
        "week_ids": [week.id],
        "enabled_types": ["Лекция", "Семинар", "Лабораторная"],
        "rule": {
            "lectures": 1,
            "seminars": 1,
            "laboratories": 1,
            "days_per_week": 2,
            "weekdays": [],
            "days_hard": False,
            "lecture_before_practice": True,
            "time_preference": "day",
        },
    }
    response = await api_client.put("/api/v1/scheduler/subject-rules", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["can_save"] is True
    assert any(item["type"] == "lec" for item in body["preview"])
    assert any(item["type"] == "sem" for item in body["preview"])
    assert any(item["type"] == "lab" for item in body["preview"])

    monkeypatch.setattr(
        scheduler.generate_schedule_task,
        "delay",
        lambda *args: SimpleNamespace(id="bio-task"),
    )
    generated = await api_client.post(
        "/api/v1/scheduler/generate",
        json={
            "groups": all_groups,
            "planning_week_id": week.id,
            "settings": {"enabled_types": ["Лекция", "Семинар", "Лабораторная"]},
        },
    )
    assert generated.status_code == 200, generated.text
    task = await db_session.get(GenerationTask, generated.json()["task_id"])
    settings = json.loads(task.settings_json)
    assert sorted(rule["group_name"] for rule in settings["subject_rules"]) == [
        "ИОП-ИТ-25/1 (L1)",
        "ИОП-ИТ-25/1 (L2)",
        "ИОП-ИТ-25/2 (L1)",
        "ИОП-ИТ-25/2 (L2)",
    ]


async def test_single_week_rule_rebalances_unfixed_semester_demands(
    api_client, db_session, subject_data
):
    _, streams, period = subject_data
    await PlanningService.distribute_semester_demands(
        period.id, ["A"], ["Лекция", "Семинар"], set(), db_session
    )
    week = period.weeks[0]
    payload = request_for(period, hard=False, days=[0, 2], seminars=3)
    payload["end_date"] = week.ends_on.isoformat()
    payload["week_ids"] = [week.id]

    response = await api_client.put("/api/v1/scheduler/subject-rules", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["can_save"] is True

    seminar_demands = list(
        (
            await db_session.execute(
                select(WeeklyLessonDemand).where(
                    WeeklyLessonDemand.stream_id == streams[1].id
                )
            )
        ).scalars()
    )
    assert sum(item.lessons_count for item in seminar_demands) == 4


async def test_fit_to_plan_distributes_short_subject_across_semester_weeks(
    api_client, db_session, monkeypatch
):
    batch = ImportBatch(filename="bio-semester.xlsx", file_type=FileType.STREAMS)
    teacher = Teacher(name="Минияров Ф.Т.")
    db_session.add_all([batch, teacher])
    await db_session.flush()

    lecture = Stream(
        import_batch_id=batch.id,
        teacher_id=teacher.id,
        event_name="Биология",
        stream_type="Лекция",
        lessons_count=5,
    )
    db_session.add(lecture)
    await db_session.flush()
    db_session.add(
        StreamGroup(stream_id=lecture.id, group_name="ИОП-ИТ-25/1", group_size=22)
    )

    seminar = Stream(
        import_batch_id=batch.id,
        teacher_id=teacher.id,
        event_name="Биология",
        stream_type="Семинар",
        lessons_count=3,
    )
    db_session.add(seminar)
    await db_session.flush()
    db_session.add(
        StreamGroup(stream_id=seminar.id, group_name="ИОП-ИТ-25/1", group_size=22)
    )

    for subgroup in ("L1", "L2"):
        lab = Stream(
            import_batch_id=batch.id,
            teacher_id=teacher.id,
            event_name="Биология",
            stream_type="Лабораторная",
            lessons_count=3,
        )
        db_session.add(lab)
        await db_session.flush()
        db_session.add(
            StreamGroup(
                stream_id=lab.id,
                group_name=f"ИОП-ИТ-25/1 ({subgroup})",
                group_size=11,
            )
        )

    period = await PlanningService.create_period(
        AcademicPeriodCreate(
            name="Семестр 13 нед.",
            starts_on=datetime.date(2026, 9, 7),
            ends_on=datetime.date(2026, 12, 6),
        ),
        db_session,
    )
    await db_session.commit()
    assert len(period.weeks) == 13

    groups = ["ИОП-ИТ-25/1", "ИОП-ИТ-25/1 (L1)", "ИОП-ИТ-25/1 (L2)"]
    payload = {
        "subject": "Биология",
        "groups": groups,
        "start_date": period.starts_on.isoformat(),
        "end_date": period.ends_on.isoformat(),
        "week_ids": [week.id for week in period.weeks],
        "enabled_types": ["Лекция", "Семинар", "Лабораторная"],
        "rule": {
            "lectures": 1,
            "seminars": 1,
            "laboratories": 1,
            "days_per_week": 2,
            "weekdays": [],
            "days_hard": False,
            "lecture_before_practice": True,
            "time_preference": "day",
            "fit_to_plan": True,
        },
    }
    response = await api_client.put("/api/v1/scheduler/subject-rules", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["can_save"] is True
    assert body["preview"]
    assert any("5 из 13 недель" in warning for warning in body["warnings"])

    monkeypatch.setattr(
        scheduler.generate_schedule_task,
        "delay",
        lambda *args: SimpleNamespace(id="fit-task"),
    )
    # Both active week (week 1) and empty week (week 10) must generate cleanly.
    for week in (period.weeks[0], period.weeks[9]):
        generated = await api_client.post(
            "/api/v1/scheduler/generate",
            json={
                "groups": groups,
                "planning_week_id": week.id,
                "settings": {"enabled_types": ["Лекция", "Семинар", "Лабораторная"]},
            },
        )
        assert generated.status_code == 200, generated.text
