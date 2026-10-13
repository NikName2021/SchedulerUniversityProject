from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from api.routes.api import router as api_router
from api.routes.scheduler import UPLOAD_DIR
from core.config import (
    ALLOWED_HOSTS,
    API_PREFIX,
    AUTO_CREATE_TABLES,
    CORS_ORIGINS,
    DATABASE_SCHEMA_REVISION,
    DEBUG,
    DEFAULT_USERS_FILE,
    HOST,
    PORT,
    PROJECT_NAME,
    VERSION,
    async_get_db,
    engine,
    logger,
    sessionmaker,
)
from database import create_tables
from database.workspace import WorkspaceAccessError
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from middleware import LoggingMiddleware, SecurityHeadersMiddleware
from services.default_users_service import bootstrap_default_users
from services.upload_service import purge_legacy_uploads
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.trustedhost import TrustedHostMiddleware


@asynccontextmanager
async def application_lifespan(_application: FastAPI):
    if AUTO_CREATE_TABLES:
        await create_tables(engine)
    else:
        # Only clean legacy files after the destructive database migration.
        try:
            async with sessionmaker() as db:
                revision = await db.scalar(
                    text("SELECT version_num FROM alembic_version")
                )
        except SQLAlchemyError:
            revision = None
            logger.warning(
                "Could not read the database migration revision; "
                "legacy upload cleanup was skipped",
                exc_info=True,
            )
        if revision == DATABASE_SCHEMA_REVISION:
            removed = purge_legacy_uploads(UPLOAD_DIR)
            if removed:
                logger.info("Removed %s legacy shared uploads", removed)
    if DEFAULT_USERS_FILE:
        async with sessionmaker() as db:
            created = await bootstrap_default_users(DEFAULT_USERS_FILE, db)
        if created:
            logger.info("Created default user accounts: %s", ", ".join(created))
    yield


def get_application() -> FastAPI:
    application = FastAPI(
        title=PROJECT_NAME, debug=DEBUG, version=VERSION, lifespan=application_lifespan
    )
    application.include_router(api_router, prefix=API_PREFIX)

    @application.exception_handler(WorkspaceAccessError)
    async def workspace_access_error(_request, _exc):
        return JSONResponse(status_code=404, content={"detail": "Object not found"})

    application.add_middleware(LoggingMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health/live", include_in_schema=False)
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready", include_in_schema=False)
    async def health_ready(
        db: Annotated[AsyncSession, Depends(async_get_db)],
    ) -> dict[str, str]:
        try:
            result = await db.execute(text("SELECT version_num FROM alembic_version"))
            if result.scalar_one_or_none() != DATABASE_SCHEMA_REVISION:
                raise RuntimeError("Database migration revision is not current")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database is unavailable or requires migration",
            ) from exc
        return {"status": "ready"}

    return application


app = get_application()

if __name__ == "__main__":
    uvicorn.run(get_application(), host=HOST, port=PORT)
