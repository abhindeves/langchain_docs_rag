from fastapi import FastAPI, HTTPException, status
from qdrant_client import QdrantClient

from shared.config import get_shared_settings

app = FastAPI(
    title=" RAG API Service", description="Production-grade RAG API", version="0.1.0"
)

settings = get_shared_settings()


@app.get("/health/liveness", status_code=status.HTTP_200_OK)
async def liveness():
    """Simple liveness check to ensure the service is running."""
    return {"status": "ok", "service": "api-service"}


@app.get("/health/readiness", status_code=status.HTTP_200_OK)
async def readiness():
    """Readiness check that verifies connectivity to the Qdrant database."""
    try:
        # Initialize client using host and port from settings
        client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key,
            timeout=2,  # short timeout for quick health check
        )
        # Verify connection by listing collections (a quick read check)
        client.get_collections()
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Qdrant database is not reachable: {str(e)}",
        ) from e
