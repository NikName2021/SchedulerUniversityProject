from typing import Any

from database import (
    ActivityType,
    AvailabilityRule,
    Building,
    Department,
    Discipline,
    Room,
    RoomFeature,
    RoomFeatureLink,
    RuleProfile,
    RuleSetting,
    Stream,
    StreamFeatureRequirement,
    StudentGroup,
    Teacher,
)
from schemas.reference import (
    AvailabilityRuleCreate,
    RoomCreate,
    RoomRead,
    RoomUpdate,
    RuleProfileCreate,
    RuleSettingInput,
    StreamRequirementsUpdate,
    StudentGroupProfileUpdate,
    TeacherProfileUpdate,
)
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class ReferenceService:
    @staticmethod
    async def _require_entity(
        model: type[Any], entity_id: int | None, db: AsyncSession
    ) -> None:
        if entity_id is not None and await db.get(model, entity_id) is None:
            raise LookupError(f"{model.__name__} {entity_id} not found")

    @staticmethod
    async def list_rooms(db: AsyncSession) -> list[Room]:
        result = await db.execute(
            select(Room)
            .options(
                selectinload(Room.building),
                selectinload(Room.feature_links).selectinload(RoomFeatureLink.feature),
            )
            .order_by(Room.code)
        )
        return list(result.scalars().unique())

    @staticmethod
    def room_to_schema(room: Room) -> RoomRead:
        return RoomRead(
            id=room.id,
            building_id=room.building_id,
            building_name=room.building.name if room.building else None,
            owner_department_id=room.owner_department_id,
            code=room.code,
            name=room.name,
            floor=room.floor,
            capacity=room.capacity,
            room_type=room.room_type,
            is_active=room.is_active,
            features=[link.feature for link in room.feature_links],
        )

    @staticmethod
    async def _validate_feature_ids(feature_ids: list[int], db: AsyncSession) -> None:
        unique_ids = set(feature_ids)
        if len(unique_ids) != len(feature_ids):
            raise ValueError("feature_ids must be unique")
        if not unique_ids:
            return
        result = await db.execute(
            select(RoomFeature.id).where(RoomFeature.id.in_(unique_ids))
        )
        missing = unique_ids - set(result.scalars())
        if missing:
            raise LookupError(f"Unknown room features: {sorted(missing)}")

    @staticmethod
    async def create_room(payload: RoomCreate, db: AsyncSession) -> Room:
        await ReferenceService._require_entity(Building, payload.building_id, db)
        await ReferenceService._require_entity(
            Department, payload.owner_department_id, db
        )
        await ReferenceService._validate_feature_ids(payload.feature_ids, db)
        room = Room(**payload.model_dump(exclude={"feature_ids"}))
        db.add(room)
        await db.flush()
        db.add_all(
            [
                RoomFeatureLink(room_id=room.id, feature_id=feature_id)
                for feature_id in payload.feature_ids
            ]
        )
        await db.commit()
        rooms = await ReferenceService.list_rooms(db)
        return next(item for item in rooms if item.id == room.id)

    @staticmethod
    async def update_room(room: Room, payload: RoomUpdate, db: AsyncSession) -> Room:
        values = payload.model_dump(exclude_unset=True, exclude={"feature_ids"})
        await ReferenceService._require_entity(Building, values.get("building_id"), db)
        await ReferenceService._require_entity(
            Department, values.get("owner_department_id"), db
        )
        for field, value in values.items():
            setattr(room, field, value)
        if payload.feature_ids is not None:
            await ReferenceService._validate_feature_ids(payload.feature_ids, db)
            await db.execute(
                delete(RoomFeatureLink).where(RoomFeatureLink.room_id == room.id)
            )
            db.add_all(
                [
                    RoomFeatureLink(room_id=room.id, feature_id=feature_id)
                    for feature_id in payload.feature_ids
                ]
            )
        await db.commit()
        rooms = await ReferenceService.list_rooms(db)
        return next(item for item in rooms if item.id == room.id)

    @staticmethod
    async def create_availability_rule(
        payload: AvailabilityRuleCreate, db: AsyncSession
    ) -> AvailabilityRule:
        scope_models: list[tuple[int | None, type[Any]]] = [
            (payload.teacher_id, Teacher),
            (payload.student_group_id, StudentGroup),
            (payload.room_id, Room),
        ]
        for resource_id, model in scope_models:
            await ReferenceService._require_entity(model, resource_id, db)
        rule = AvailabilityRule(**payload.model_dump())
        db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return rule

    @staticmethod
    async def create_rule_profile(
        payload: RuleProfileCreate, db: AsyncSession
    ) -> RuleProfile:
        if payload.is_default:
            await db.execute(update(RuleProfile).values(is_default=False))
        profile = RuleProfile(**payload.model_dump(exclude={"settings"}))
        db.add(profile)
        await db.flush()
        await ReferenceService.replace_rule_settings(
            profile.id, payload.settings, db, commit=False
        )
        await db.commit()
        return await ReferenceService.get_rule_profile(profile.id, db)

    @staticmethod
    async def get_rule_profile(profile_id: int, db: AsyncSession) -> RuleProfile | None:
        result = await db.execute(
            select(RuleProfile)
            .where(RuleProfile.id == profile_id)
            .options(selectinload(RuleProfile.settings))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_rule_profiles(db: AsyncSession) -> list[RuleProfile]:
        result = await db.execute(
            select(RuleProfile)
            .options(selectinload(RuleProfile.settings))
            .order_by(RuleProfile.is_default.desc(), RuleProfile.name)
        )
        return list(result.scalars().unique())

    @staticmethod
    async def replace_rule_settings(
        profile_id: int,
        settings: list[RuleSettingInput],
        db: AsyncSession,
        commit: bool = True,
    ) -> None:
        codes = [setting.rule_code for setting in settings]
        if len(codes) != len(set(codes)):
            raise ValueError("rule_code values must be unique")
        await db.execute(
            delete(RuleSetting).where(RuleSetting.profile_id == profile_id)
        )
        db.add_all(
            [
                RuleSetting(profile_id=profile_id, **setting.model_dump())
                for setting in settings
            ]
        )
        if commit:
            await db.commit()

    @staticmethod
    async def update_teacher_profile(
        teacher: Teacher, payload: TeacherProfileUpdate, db: AsyncSession
    ) -> Teacher:
        values = payload.model_dump(exclude_unset=True)
        await ReferenceService._require_entity(
            Department, values.get("department_id"), db
        )
        for field, value in values.items():
            setattr(teacher, field, value)
        await db.commit()
        await db.refresh(teacher)
        return teacher

    @staticmethod
    async def update_group_profile(
        group: StudentGroup,
        payload: StudentGroupProfileUpdate,
        db: AsyncSession,
    ) -> StudentGroup:
        values = payload.model_dump(exclude_unset=True)
        min_load = values.get("min_weekly_lessons", group.min_weekly_lessons)
        max_load = values.get("max_weekly_lessons", group.max_weekly_lessons)
        if min_load is not None and max_load is not None and min_load > max_load:
            raise ValueError("min_weekly_lessons must not exceed max_weekly_lessons")
        for field, value in values.items():
            setattr(group, field, value)
        await db.commit()
        await db.refresh(group)
        return group

    @staticmethod
    async def update_stream_requirements(
        stream: Stream,
        payload: StreamRequirementsUpdate,
        db: AsyncSession,
    ) -> Stream:
        values = payload.model_dump(exclude_unset=True, exclude={"feature_ids"})
        await ReferenceService._require_entity(
            Discipline, values.get("discipline_id"), db
        )
        await ReferenceService._require_entity(
            ActivityType, values.get("activity_type_id"), db
        )
        await ReferenceService._require_entity(Room, values.get("required_room_id"), db)
        for field, value in values.items():
            setattr(stream, field, value)
        if payload.feature_ids is not None:
            await ReferenceService._validate_feature_ids(payload.feature_ids, db)
            await db.execute(
                delete(StreamFeatureRequirement).where(
                    StreamFeatureRequirement.stream_id == stream.id
                )
            )
            db.add_all(
                [
                    StreamFeatureRequirement(
                        stream_id=stream.id,
                        feature_id=feature_id,
                    )
                    for feature_id in payload.feature_ids
                ]
            )
        await db.commit()
        result = await db.execute(
            select(Stream)
            .where(Stream.id == stream.id)
            .options(selectinload(Stream.feature_requirements))
        )
        return result.scalar_one()
