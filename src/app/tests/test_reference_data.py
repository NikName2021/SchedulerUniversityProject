import datetime

import pytest
from database import AvailabilityRule, Room, StudentGroup
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
