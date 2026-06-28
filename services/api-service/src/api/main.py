from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

from rag_shared.config import get_shared_settings
from rag_shared.embeddings import Embedder

app = FastAPI(title=" RAG API Service", description="Production-grade RAG API", version="0.1.0")

settings = get_shared_settings()

# Initialize the Embedder client once at startup (Singleton pattern).
# This reuses the boto3 client connection pool and shares the
# global concurrency semaphore.
embedder = Embedder()


class EmbedRequest(BaseModel):
    text: str = Field(..., description="The text to generate embeddings for.")


@app.get("/health/liveness", status_code=status.HTTP_200_OK)
async def liveness():
    """Simple liveness check to ensure the service is running."""
    return {"status": "ok", "service": "api-service"}


@app.get("/health/readiness", status_code=status.HTTP_200_OK)
async def readiness():
    """Readiness check that verifies connectivity to the Qdrant database."""
    try:
        if not settings.qdrant_host:
            raise ValueError("Qdrant host URL is not configured.")
        client = QdrantClient(
            url=settings.qdrant_host,
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


@app.post("/embed", status_code=status.HTTP_200_OK)
async def embed_function(request: EmbedRequest):
    """Embed text and return the embedding vector."""
    try:
        vector = await embedder.embed_query(request.text)
        return {"embedding": vector}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to embed text: {str(e)}",
        ) from e
