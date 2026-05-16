import time
import uuid

from core.config import logger
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        logging_dict = {
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_host": request.client.host,
            "client_port": request.client.port,
        }

        start_time = time.time()

        response = None
        try:
            response = await call_next(request)
            logging_dict["status_code"] = response.status_code
        except Exception as e:
            logging_dict["status_code"] = 500
            logger.error(
                "Unhandled exception",
                extra={
                    "log_type": "request_log",
                    "request_id": request_id,
                    "request_details": logging_dict,
                },
                exc_info=e,
            )
            raise e
        finally:
            process_time = (time.time() - start_time) * 1000
            logging_dict["process_time_ms"] = round(process_time)

            logger.info(
                "Request processed",
                extra={
                    "log_type": "request_log",
                    "request_id": request_id,
                    "request_details": logging_dict,
                },
            )

            if response:
                response.headers["X-Request-ID"] = request_id

            return response
