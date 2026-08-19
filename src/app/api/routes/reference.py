from typing import Annotated, Any

from core.config import async_get_db
from database import (
    ActivityType,
    AvailabilityRule,
    Building,
    Department,
    Discipline,
    Room,
    RoomFeature,
    Stream,
    StudentGroup,
    Teacher,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from schemas.reference import (
    ActivityTypeCreate,
    ActivityTypeRead,
    AvailabilityRuleCreate,
    AvailabilityRuleRead,
    BuildingCreate,
    BuildingRead,
    DepartmentCreate,
    DepartmentRead,
    DisciplineCreate,
    DisciplineRead,
    RoomCreate,
    RoomFeatureCreate,
    RoomFeatureRead,
    RoomRead,
    RoomUpdate,
    RuleProfileCreate,
    RuleProfileDetailsRead,
    RuleProfileRead,
    RuleSettingsUpdate,
    StreamRequirementsRead,
    StreamRequirementsUpdate,
    StudentGroupProfileRead,
    StudentGroupProfileUpdate,
    TeacherProfileRead,
    TeacherProfileUpdate,
)
from services.reference_service import ReferenceService
from services.rule_catalog_service import describe_rule_profile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/reference", tags=["Reference data"])


async def _commit_created(entity: Any, db: AsyncSession) -> Any:
    db.add(entity)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Reference value already exists"
        ) from exc
    await db.refresh(entity)
    return entity


@router.get("/departments", response_model=list[DepartmentRead])
async def list_departments(
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> list[DepartmentRead]:
    result = await db.execute(select(Department).order_by(Department.name))
    return [DepartmentRead.model_validate(item) for item in result.scalars()]


@router.post(
    "/departments", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED
)
async def create_department(
    payload: DepartmentCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> DepartmentRead:
    item = await _commit_created(Department(**payload.model_dump()), db)
    return DepartmentRead.model_validate(item)


@router.get("/buildings", response_model=list[BuildingRead])
async def list_buildings(
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> list[BuildingRead]:
    result = await db.execute(select(Building).order_by(Building.name))
    return [BuildingRead.model_validate(item) for item in result.scalars()]


@router.post(
    "/buildings", response_model=BuildingRead, status_code=status.HTTP_201_CREATED
)
async def create_building(
    payload: BuildingCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> BuildingRead:
    item = await _commit_created(Building(**payload.model_dump()), db)
    return BuildingRead.model_validate(item)


@router.get("/room-features", response_model=list[RoomFeatureRead])
async def list_room_features(
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> list[RoomFeatureRead]:
    result = await db.execute(select(RoomFeature).order_by(RoomFeature.name))
    return [RoomFeatureRead.model_validate(item) for item in result.scalars()]


@router.post(
    "/room-features",
    response_model=RoomFeatureRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_room_feature(
    payload: RoomFeatureCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> RoomFeatureRead:
    item = await _commit_created(RoomFeature(**payload.model_dump()), db)
    return RoomFeatureRead.model_validate(item)


@router.get("/activity-types", response_model=list[ActivityTypeRead])
async def list_activity_types(
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> list[ActivityTypeRead]:
    result = await db.execute(select(ActivityType).order_by(ActivityType.name))
    return [ActivityTypeRead.model_validate(item) for item in result.scalars()]


@router.post(
    "/activity-types",
    response_model=ActivityTypeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_activity_type(
    payload: ActivityTypeCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> ActivityTypeRead:
    item = await _commit_created(ActivityType(**payload.model_dump()), db)
    return ActivityTypeRead.model_validate(item)


@router.get("/disciplines", response_model=list[DisciplineRead])
async def list_disciplines(
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> list[DisciplineRead]:
    result = await db.execute(select(Discipline).order_by(Discipline.full_name))
    return [DisciplineRead.model_validate(item) for item in result.scalars()]


@router.post(
    "/disciplines",
    response_model=DisciplineRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_discipline(
    payload: DisciplineCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> DisciplineRead:
    item = await _commit_created(Discipline(**payload.model_dump()), db)
    return DisciplineRead.model_validate(item)


@router.get("/rooms", response_model=list[RoomRead])
async def list_rooms(
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> list[RoomRead]:
    rooms = await ReferenceService.list_rooms(db)
    return [ReferenceService.room_to_schema(room) for room in rooms]


@router.post("/rooms", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
async def create_room(
    payload: RoomCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> RoomRead:
    try:
        room = await ReferenceService.create_room(payload, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Room already exists") from exc
    return ReferenceService.room_to_schema(room)


@router.patch("/rooms/{room_id}", response_model=RoomRead)
async def update_room(
    room_id: int,
    payload: RoomUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> RoomRead:
    room = await db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        room = await ReferenceService.update_room(room, payload, db)
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ReferenceService.room_to_schema(room)


@router.get("/availability", response_model=list[AvailabilityRuleRead])
async def list_availability_rules(
    db: Annotated[AsyncSession, Depends(async_get_db)],
    teacher_id: Annotated[int | None, Query()] = None,
    student_group_id: Annotated[int | None, Query()] = None,
    room_id: Annotated[int | None, Query()] = None,
) -> list[AvailabilityRuleRead]:
    query = select(AvailabilityRule).order_by(AvailabilityRule.id)
    if teacher_id is not None:
        query = query.where(AvailabilityRule.teacher_id == teacher_id)
    if student_group_id is not None:
        query = query.where(AvailabilityRule.student_group_id == student_group_id)
    if room_id is not None:
        query = query.where(AvailabilityRule.room_id == room_id)
    result = await db.execute(query)
    return [AvailabilityRuleRead.model_validate(item) for item in result.scalars()]


@router.post(
    "/availability",
    response_model=AvailabilityRuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_availability_rule(
    payload: AvailabilityRuleCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> AvailabilityRuleRead:
    try:
        rule = await ReferenceService.create_availability_rule(payload, db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AvailabilityRuleRead.model_validate(rule)


@router.delete("/availability/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_availability_rule(
    rule_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> None:
    rule = await db.get(AvailabilityRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Availability rule not found")
    await db.delete(rule)
    await db.commit()


@router.get("/rule-profiles", response_model=list[RuleProfileRead])
async def list_rule_profiles(
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> list[RuleProfileRead]:
    profiles = await ReferenceService.list_rule_profiles(db)
    return [RuleProfileRead.model_validate(profile) for profile in profiles]


@router.get(
    "/rule-profiles/{profile_id}/details", response_model=RuleProfileDetailsRead
)
async def get_rule_profile_details(
    profile_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> RuleProfileDetailsRead:
    profile = await ReferenceService.get_rule_profile(profile_id, db)
    if profile is None:
        raise HTTPException(status_code=404, detail="Rule profile not found")
    return RuleProfileDetailsRead(
        profile=RuleProfileRead.model_validate(profile),
        rules=describe_rule_profile(profile.settings),
    )


@router.post(
    "/rule-profiles",
    response_model=RuleProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_rule_profile(
    payload: RuleProfileCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> RuleProfileRead:
    try:
        profile = await ReferenceService.create_rule_profile(payload, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Rule profile already exists"
        ) from exc
    return RuleProfileRead.model_validate(profile)


@router.put("/rule-profiles/{profile_id}/settings", response_model=RuleProfileRead)
async def replace_rule_settings(
    profile_id: int,
    payload: RuleSettingsUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> RuleProfileRead:
    profile = await ReferenceService.get_rule_profile(profile_id, db)
    if profile is None:
        raise HTTPException(status_code=404, detail="Rule profile not found")
    try:
        await ReferenceService.replace_rule_settings(profile_id, payload.settings, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    profile = await ReferenceService.get_rule_profile(profile_id, db)
    return RuleProfileRead.model_validate(profile)


@router.patch("/teachers/{teacher_id}", response_model=TeacherProfileRead)
async def update_teacher_profile(
    teacher_id: int,
    payload: TeacherProfileUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> TeacherProfileRead:
    teacher = await db.get(Teacher, teacher_id)
    if teacher is None:
        raise HTTPException(status_code=404, detail="Teacher not found")
    try:
        teacher = await ReferenceService.update_teacher_profile(teacher, payload, db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TeacherProfileRead.model_validate(teacher)


@router.patch("/groups/{group_id}", response_model=StudentGroupProfileRead)
async def update_group_profile(
    group_id: int,
    payload: StudentGroupProfileUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> StudentGroupProfileRead:
    group = await db.get(StudentGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Student group not found")
    try:
        group = await ReferenceService.update_group_profile(group, payload, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StudentGroupProfileRead.model_validate(group)


@router.patch(
    "/streams/{stream_id}/requirements", response_model=StreamRequirementsRead
)
async def update_stream_requirements(
    stream_id: int,
    payload: StreamRequirementsUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> StreamRequirementsRead:
    stream = await db.get(Stream, stream_id)
    if stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")
    try:
        stream = await ReferenceService.update_stream_requirements(stream, payload, db)
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    feature_ids = [item.feature_id for item in stream.feature_requirements]
    return StreamRequirementsRead(
        id=stream.id,
        discipline_id=stream.discipline_id,
        activity_type_id=stream.activity_type_id,
        required_room_id=stream.required_room_id,
        starts_on=stream.starts_on,
        ends_on=stream.ends_on,
        feature_ids=feature_ids,
    )
