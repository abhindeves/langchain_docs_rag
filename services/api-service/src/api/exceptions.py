import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("api_service")


def setup_exception_handler(app: FastAPI):
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Internal server error: {str(exc)}")

        correlation_id = getattr(request.state, "correlation_id", "unknown")

        logger.error(f"Unhandled execption occured, CorrelationID={correlation_id} " f"Error={str(exc)}", exc_info=True)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal Server Error", "message": "An unexpected error occured. Please contact Support", "correlation_id": correlation_id},
        )
