import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api_service")


class CorrelationAndTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()

        correlation_id = request.headers.get("x-correlation-id", str(uuid.uuid4()))
        correlation_id = correlation_id.replace("\r", "").replace("\n", "")

        request.state.correlation_id = correlation_id

        response = await call_next(request)

        process_time = time.perf_counter() - start_time

        response.headers["x-correlation-id"] = correlation_id
        response.headers["x-process-time"] = str(process_time)

        logger.info(f"Method={request.method} Path={request.url.path} Status={response.status_code} Time={process_time:.4f}sCorrID={correlation_id}")
        return response
