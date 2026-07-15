import logging

from api.config import get_api_settings
from fastapi import APIRouter, HTTPException, Request, status
from qdrant_client import AsyncQdrantClient

router = APIRouter(prefix="/health", tags=["health"])
settings = get_api_settings()


@router.get("/liveness", status_code=status.HTTP_200_OK)
async def liveness():
    """Simple liveness check to ensure the service is running."""
    return {"status": "ok", "service": "api-service"}


@router.get("/readiness", status_code=status.HTTP_200_OK)
async def readiness(request: Request):
    """Readiness check that verifies connectivity to the Qdrant database."""
    try:
        if not settings.qdrant_host:
            raise ValueError("Qdrant host URL is not configured.")

        # Access the high-performance connection pool client stored in app.state
        client: AsyncQdrantClient = request.app.state.qdrant_client

        # Verify connection asynchronously by listing collections (quick read check)
        await client.get_collections()
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logging.error(f"Qdrant database is not reachable: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Qdrant database is not reachable: {str(e)}",
        ) from e
