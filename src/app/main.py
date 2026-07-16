import uvicorn
from api.routes.api import router as api_router
from core.config import (
    API_PREFIX,
    AUTO_CREATE_TABLES,
    CORS_ORIGINS,
    DEBUG,
    HOST,
    PORT,
    PROJECT_NAME,
    VERSION,
    engine,
)
from database import create_tables
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from middleware import LoggingMiddleware
from sqlalchemy import text


def get_application() -> FastAPI:
    application = FastAPI(title=PROJECT_NAME, debug=DEBUG, version=VERSION)
    application.include_router(api_router, prefix=API_PREFIX)
    application.add_middleware(LoggingMiddleware)
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
    async def health_ready() -> dict[str, str]:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database is unavailable",
            ) from exc
        return {"status": "ready"}

    return application


app = get_application()

if __name__ == "__main__":
    uvicorn.run(get_application(), host=HOST, port=PORT)
