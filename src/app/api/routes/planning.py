from typing import Annotated

from core.config import async_get_db
from database import PlanningWeek, WeeklyLessonDemand
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.planning import (
    AcademicPeriodCreate,
    AcademicPeriodRead,
    PlanningWeekRead,
    WeeklyDemandBulkUpdate,
    WeeklyDemandCloneRequest,
    WeeklyDemandList,
    WeeklyDemandRead,
    WeeklyDemandUpdateResult,
)
from services.planning_service import PlanningService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/planning", tags=["Planning"])


@router.post(
    "/periods",
    response_model=AcademicPeriodRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_period(
    payload: AcademicPeriodCreate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> AcademicPeriodRead:
    period = await PlanningService.create_period(payload, db)
    return AcademicPeriodRead.model_validate(period)


@router.get("/periods", response_model=list[AcademicPeriodRead])
async def list_periods(
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> list[AcademicPeriodRead]:
    periods = await PlanningService.list_periods(db)
    return [AcademicPeriodRead.model_validate(period) for period in periods]


@router.get("/periods/{period_id}/weeks", response_model=list[PlanningWeekRead])
async def list_period_weeks(
    period_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> list[PlanningWeekRead]:
    period = await PlanningService.get_period(period_id, db)
    if period is None:
        raise HTTPException(status_code=404, detail="Academic period not found")
    return [PlanningWeekRead.model_validate(week) for week in period.weeks]


async def _require_week(week_id: int, db: AsyncSession) -> PlanningWeek:
    week = await db.get(PlanningWeek, week_id)
    if week is None:
        raise HTTPException(status_code=404, detail="Planning week not found")
    return week


@router.get("/weeks/{week_id}/demands", response_model=WeeklyDemandList)
async def list_weekly_demands(
    week_id: int,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> WeeklyDemandList:
    await _require_week(week_id, db)
    result = await db.execute(
        select(WeeklyLessonDemand)
        .where(WeeklyLessonDemand.week_id == week_id)
        .order_by(WeeklyLessonDemand.stream_id)
    )
    demands = [WeeklyDemandRead.model_validate(item) for item in result.scalars()]
    return WeeklyDemandList(week_id=week_id, demands=demands)


@router.put("/weeks/{week_id}/demands", response_model=WeeklyDemandUpdateResult)
async def replace_weekly_demands(
    week_id: int,
    payload: WeeklyDemandBulkUpdate,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> WeeklyDemandUpdateResult:
    await _require_week(week_id, db)
    try:
        count = await PlanningService.replace_weekly_demands(
            week_id, payload.demands, db
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WeeklyDemandUpdateResult(week_id=week_id, updated=count)


@router.post("/weeks/{week_id}/demands/clone", response_model=WeeklyDemandUpdateResult)
async def clone_weekly_demands(
    week_id: int,
    payload: WeeklyDemandCloneRequest,
    db: Annotated[AsyncSession, Depends(async_get_db)],
) -> WeeklyDemandUpdateResult:
    await _require_week(week_id, db)
    if payload.source_week_id is not None:
        await _require_week(payload.source_week_id, db)
    try:
        count = await PlanningService.clone_weekly_demands(
            week_id,
            db,
            source_week_id=payload.source_week_id,
            use_stream_defaults=payload.use_stream_defaults,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return WeeklyDemandUpdateResult(week_id=week_id, updated=count)
