import datetime

import pytest
from database import AvailabilityRule, Room, RuleProfile, RuleSetting, StudentGroup
from httpx import AsyncClient
from schemas.reference import AvailabilityRuleCreate, RoomCreate
from services.availability_service import build_availability_context
from services.reference_service import ReferenceService
from sqlalchemy.ext.asyncio import AsyncSession


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
    context = await build_availability_context(
        db_session, "2026-09-07", "2026-09-07"
    )

    assert isinstance(room, Room)
    assert room.code == "LAB-42"
    assert context["unavailable"]["group"]["ИВТ-101"] == [
        ["2026-09-07", 1],
        ["2026-09-07", 2],
    ]
    assert await db_session.get(AvailabilityRule, 1) is not None


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
