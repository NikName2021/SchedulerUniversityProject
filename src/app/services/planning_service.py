from datetime import timedelta

from database import AcademicPeriod, PlanningWeek, Stream, WeeklyLessonDemand
from schemas.planning import AcademicPeriodCreate, WeeklyDemandItem
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class PlanningService:
    @staticmethod
    async def create_period(
        payload: AcademicPeriodCreate, db: AsyncSession
    ) -> AcademicPeriod:
        period = AcademicPeriod(
            name=payload.name,
            period_type=payload.period_type,
            education_level=payload.education_level,
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
        )
        db.add(period)
        await db.flush()

        if payload.create_weeks:
            cursor = payload.starts_on
            sequence_number = 1
            while cursor <= payload.ends_on:
                calendar_week_end = cursor + timedelta(days=6 - cursor.weekday())
                week_end = min(calendar_week_end, payload.ends_on)
                db.add(
                    PlanningWeek(
                        period_id=period.id,
                        sequence_number=sequence_number,
                        starts_on=cursor,
                        ends_on=week_end,
                    )
                )
                cursor = week_end + timedelta(days=1)
                sequence_number += 1

        await db.commit()
        return await PlanningService.get_period(period.id, db)

    @staticmethod
    async def get_period(period_id: int, db: AsyncSession) -> AcademicPeriod | None:
        result = await db.execute(
            select(AcademicPeriod)
            .where(AcademicPeriod.id == period_id)
            .options(selectinload(AcademicPeriod.weeks))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_periods(db: AsyncSession) -> list[AcademicPeriod]:
        result = await db.execute(
            select(AcademicPeriod)
            .options(selectinload(AcademicPeriod.weeks))
            .order_by(AcademicPeriod.starts_on.desc())
        )
        return list(result.scalars().unique().all())

    @staticmethod
    async def replace_weekly_demands(
        week_id: int, demands: list[WeeklyDemandItem], db: AsyncSession
    ) -> int:
        stream_ids = {item.stream_id for item in demands}
        if len(stream_ids) != len(demands):
            raise ValueError("stream_id values must be unique")

        if stream_ids:
            result = await db.execute(
                select(Stream.id).where(Stream.id.in_(stream_ids))
            )
            existing_ids = set(result.scalars().all())
            missing = stream_ids - existing_ids
            if missing:
                raise LookupError(f"Unknown streams: {sorted(missing)}")

        await db.execute(
            delete(WeeklyLessonDemand).where(WeeklyLessonDemand.week_id == week_id)
        )
        db.add_all(
            [
                WeeklyLessonDemand(
                    week_id=week_id,
                    stream_id=item.stream_id,
                    lessons_count=item.lessons_count,
                    priority=item.priority,
                )
                for item in demands
            ]
        )
        await db.commit()
        return len(demands)

    @staticmethod
    async def clone_weekly_demands(
        week_id: int,
        db: AsyncSession,
        source_week_id: int | None = None,
        use_stream_defaults: bool = False,
    ) -> int:
        if source_week_id is not None:
            result = await db.execute(
                select(WeeklyLessonDemand).where(
                    WeeklyLessonDemand.week_id == source_week_id
                )
            )
            items = [
                WeeklyDemandItem(
                    stream_id=demand.stream_id,
                    lessons_count=demand.lessons_count,
                    priority=demand.priority,
                )
                for demand in result.scalars().all()
            ]
        elif use_stream_defaults:
            result = await db.execute(
                select(Stream).where(Stream.is_ignored.is_(False))
            )
            items = [
                WeeklyDemandItem(
                    stream_id=stream.id,
                    lessons_count=stream.lessons_count,
                )
                for stream in result.scalars().all()
            ]
        else:
            raise ValueError("source_week_id or use_stream_defaults is required")

        return await PlanningService.replace_weekly_demands(week_id, items, db)
