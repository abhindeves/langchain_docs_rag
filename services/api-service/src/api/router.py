from api.v1.chat import router as chat_router
from api.v1.retrieval import router as retrieval_router
from fastapi import APIRouter

# Define the parent router for all v1 API endpoints
api_router = APIRouter(prefix="/api/v1")

# Include the endpoints from the submodules
api_router.include_router(retrieval_router, tags=["retrieval"])
api_router.include_router(chat_router, tags=["chat"])
