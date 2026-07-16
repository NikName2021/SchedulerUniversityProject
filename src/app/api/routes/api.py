from api.routes import planning, scheduler
from fastapi import APIRouter

router = APIRouter(prefix="/v1")
router.include_router(scheduler.router)
router.include_router(planning.router)
