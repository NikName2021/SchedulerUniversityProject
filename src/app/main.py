import uvicorn
from api.routes.api import router as api_router
from core.config import (
    API_PREFIX,
    DEBUG,
    HOST,
    MEMOIZATION_FLAG,
    PORT,
    PROJECT_NAME,
    VERSION,
)
from core.events import create_start_app_handler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware import LoggingMiddleware

# origins = [
#     "http://localhost:5173"
# ]


origins = ["*"]


def get_application() -> FastAPI:
    application = FastAPI(title=PROJECT_NAME, debug=DEBUG, version=VERSION)
    application.include_router(api_router, prefix=API_PREFIX)
    application.add_middleware(LoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if MEMOIZATION_FLAG:
        application.add_event_handler("startup", create_start_app_handler(application))
    return application


app = get_application()

if __name__ == "__main__":
    uvicorn.run(get_application(), host=HOST, port=PORT)
