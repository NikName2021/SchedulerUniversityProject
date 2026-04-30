from fastapi import APIRouter

from api.routes import scheduler

router = APIRouter(prefix="/v1")
router.include_router(scheduler.router)
