from contextlib import asynccontextmanager

from api.config import get_api_settings
from api.exceptions import setup_exception_handler
from api.middleware import CorrelationAndTimingMiddleware
from api.router import api_router
from api.routes.health import router as health_router
from fastapi import FastAPI
from qdrant_client import AsyncQdrantClient

settings = get_api_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Async Qdrant Client connection pool at startup
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
app.include_router(health_router)
app.include_router(api_router)
