from api.routes import scheduler
from fastapi import APIRouter

router = APIRouter(prefix="/v1")
router.include_router(scheduler.router)
