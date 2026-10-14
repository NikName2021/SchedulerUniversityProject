import datetime
import io

import pytest
from api.routes import reference, scheduler
from database import AvailabilityRule, Room, RuleProfile, RuleSetting, StudentGroup
from httpx import AsyncClient
from openpyxl import Workbook
from schemas.reference import AvailabilityRuleCreate, RoomCreate
from services.availability_service import build_availability_context
from services.reference_service import ReferenceService
from sqlalchemy.ext.asyncio import AsyncSession


def _rooms_workbook() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Помещения"
    worksheet.append(
        [None, "Название", "Тип учебного помещения", "Вместимость", "Комментарий"]
    )
    worksheet.append([None, "Зона колледжа", None, None, None])
    worksheet.append([1, "К_0", "Лек/Прак", 35, None])
    worksheet.append([2, "Бета 3.3+3.4 (комп)", "Лек/Прак/Лаб", 12, None])
    worksheet.append([3, "EGO", "Прак (ин.яз)", 14, None])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


@pytest.mark.asyncio
async def test_room_crud_and_structured_availability(
    db_session: AsyncSession,
) -> None:
    room = await ReferenceService.create_room(
        RoomCreate(code="LAB-42", capacity=24, room_type="lab"), db_session
    )
    group = StudentGroup(name="ИВТ-101", student_count=20)
    db_session.add(group)
    await db_session.commit()

    await ReferenceService.create_availability_rule(
        AvailabilityRuleCreate(
            student_group_id=group.id,
            rule_kind="unavailable",
            recurrence="specific",
            specific_date=datetime.date(2026, 9, 7),
            lesson_start=1,
            lesson_end=2,
        ),
        db_session,
    )
    context = await build_availability_context(db_session, "2026-09-07", "2026-09-07")

    assert isinstance(room, Room)
    assert room.code == "LAB-42"
    assert context["unavailable"]["group"]["ИВТ-101"] == [
        ["2026-09-07", 1],
        ["2026-09-07", 2],
    ]
    assert await db_session.get(AvailabilityRule, 1) is not None


@pytest.mark.asyncio
async def test_room_workbook_import_recognizes_supplied_layout(
    api_client: AsyncClient,
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(reference, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(scheduler, "UPLOAD_DIR", tmp_path)
    workbook_content = _rooms_workbook()
    response = await api_client.post(
        "/api/v1/reference/rooms/import",
        files={
            "file": (
                "Помещения — копия.xlsx",
                workbook_content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    batch_id = payload.pop("batch_id")
    assert payload == {
        "rooms_found": 3,
        "rooms_created": 3,
        "rooms_updated": 0,
    }
    history = await api_client.get(
        "/api/v1/scheduler/import/history", params={"file_type": "rooms"}
    )
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [batch_id]
    assert history.json()[0]["filename"] == "Помещения — копия.xlsx"
    assert (
        await api_client.get(
            "/api/v1/scheduler/import/history", params={"file_type": "streams"}
        )
    ).json() == []
    download = await api_client.get(
        f"/api/v1/scheduler/import/history/{batch_id}/download"
    )
    assert download.status_code == 200
    assert download.content == workbook_content
    assert "filename*=utf-8''" in download.headers["content-disposition"].lower()
    rooms = {
        room["code"]: room
        for room in (await api_client.get("/api/v1/reference/rooms")).json()
    }
    assert rooms["К_0"]["capacity"] == 35
    assert rooms["К_0"]["room_type"] == "mixed"
    assert rooms["Бета 3.3+3.4 (комп)"]["room_type"] == "mixed"
    assert rooms["EGO"]["room_type"] == "sem"


@pytest.mark.asyncio
async def test_rule_profile_details_describe_actual_generator_state(
    db_session: AsyncSession,
    api_client: AsyncClient,
) -> None:
    profile = RuleProfile(
        name="Стандартный",
        description="Базовый профиль",
        is_default=True,
        is_active=True,
    )
    db_session.add(profile)
    await db_session.flush()
    db_session.add_all(
        [
            RuleSetting(
                profile_id=profile.id,
                rule_code="double_booking",
                enabled=True,
                is_hard=True,
                weight=10,
            ),
            RuleSetting(
                profile_id=profile.id,
                rule_code="minimize_windows",
                enabled=False,
                is_hard=False,
                weight=7,
            ),
            RuleSetting(
                profile_id=profile.id,
                rule_code="room_capacity",
                enabled=True,
                is_hard=False,
                weight=5,
            ),
            RuleSetting(
                profile_id=profile.id,
                rule_code="load_balance",
                enabled=True,
                is_hard=False,
                weight=5,
            ),
        ]
    )
    await db_session.commit()

    response = await api_client.get(
        f"/api/v1/reference/rule-profiles/{profile.id}/details"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["name"] == "Стандартный"
    rules = {rule["code"]: rule for rule in payload["rules"]}
    assert rules["double_booking"]["runtime_state"] == "active"
    assert rules["double_booking"]["configurable"] is False
    assert rules["minimize_windows"]["runtime_state"] == "disabled"
    assert rules["room_capacity"]["runtime_state"] == "temporarily_disabled"
    assert rules["load_balance"]["runtime_state"] == "not_implemented"
    timing = payload["solver_timing"]
    assert timing["total_component_seconds"] == 400
    assert [stage["seconds"] for stage in timing["stages"]] == [140, 140, 120]
    assert [stage["code"] for stage in timing["stages"]] == [
        "placement",
        "windows",
        "quality",
    ]


@pytest.mark.asyncio
async def test_current_rules_are_available_without_a_saved_profile(
    api_client: AsyncClient,
) -> None:
    profiles = await api_client.get("/api/v1/reference/rule-profiles")
    current = await api_client.get("/api/v1/reference/rules/current")

    assert profiles.status_code == 200
    assert profiles.json() == []
    assert current.status_code == 200
    payload = current.json()
    assert len(payload["rules"]) == 12
    assert payload["rules"][0]["code"] == "double_booking"
    assert payload["solver_timing"]["total_component_seconds"] == 400
