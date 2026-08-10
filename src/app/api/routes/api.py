from api.dependencies import require_authenticated_request
from api.routes import auth, planning, reference, scheduler
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/v1")
router.include_router(auth.router)

protected_router = APIRouter(
    dependencies=[Depends(require_authenticated_request)],
)
protected_router.include_router(scheduler.router)
protected_router.include_router(planning.router)
protected_router.include_router(reference.router)
router.include_router(protected_router)
