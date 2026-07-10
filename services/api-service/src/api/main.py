from contextlib import asynccontextmanager

from api.config import get_api_settings
from api.exceptions import setup_exception_handler
from api.middleware import CorrelationAndTimingMiddleware
from api.router import api_router
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient

from rag_shared.embeddings import Embedder

settings = get_api_settings()

# Initialize the Embedder client once at startup (Singleton pattern).
# This reuses the boto3 client connection pool and shares the
# global concurrency semaphore.
embedder = Embedder()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the high-performance Async Qdrant Client connection pool at startup
    app.state.qdrant_client = AsyncQdrantClient(
        url=settings.qdrant_host,
        api_key=settings.qdrant_api_key,
    )
    yield
    # Safely close connection pool when application shuts down
    await app.state.qdrant_client.close()


app = FastAPI(
    title="RAG API Service",
    description="Production-grade RAG API",
    version="0.1.0",
    lifespan=lifespan,
)

# Register Middleware (Correlation tracking & timings)
app.add_middleware(CorrelationAndTimingMiddleware)

# Register Exception Handlers
setup_exception_handler(app)

# Register Routes
app.include_router(api_router)


class EmbedRequest(BaseModel):
    text: str = Field(..., description="The text to generate embeddings for.")


@app.get("/health/liveness", status_code=status.HTTP_200_OK)
async def liveness():
    """Simple liveness check to ensure the service is running."""
    return {"status": "ok", "service": "api-service"}


@app.get("/health/readiness", status_code=status.HTTP_200_OK)
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
