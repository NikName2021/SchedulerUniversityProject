from typing import Annotated

import uvicorn
from api.routes.api import router as api_router
from core.config import (
    ALLOWED_HOSTS,
    API_PREFIX,
    AUTO_CREATE_TABLES,
    CORS_ORIGINS,
    DATABASE_SCHEMA_REVISION,
    DEBUG,
    HOST,
    PORT,
    PROJECT_NAME,
    VERSION,
    async_get_db,
    engine,
)
from database import create_tables
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from middleware import LoggingMiddleware, SecurityHeadersMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.trustedhost import TrustedHostMiddleware


def get_application() -> FastAPI:
    application = FastAPI(title=PROJECT_NAME, debug=DEBUG, version=VERSION)
    application.include_router(api_router, prefix=API_PREFIX)
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

    if AUTO_CREATE_TABLES:
        async def create_tables_on_startup() -> None:
            await create_tables(engine)

        application.add_event_handler("startup", create_tables_on_startup)

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
