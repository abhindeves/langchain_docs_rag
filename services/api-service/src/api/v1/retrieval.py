from typing import Any

from api.config import get_api_settings
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from qdrant_client import models

from rag_shared.embeddings import Embedder
from rag_shared.reranker import Reranker

router = APIRouter()
settings = get_api_settings()
embedder = Embedder()
reranker_client = Reranker()


class RetrieveRequest(BaseModel):
    query_text: str = Field(..., description="The query text to retrieve documents for.")
    top_k: int = Field(default=50, description="The number of documents to retrieve.")
    hybrid: bool = Field(default=True, description="Whether to use hybrid search.")
    reranker: bool = Field(default=True, description="Whether to use reranker.")
    rerank_top_k: int = Field(default=10, description="The number of documents to rerank.")
    metadata_filter: dict[str, Any] | None = Field(default=None, description="Metadata filter to apply to the search.")

    model_config = {"json_schema_extra": {"example": {"query_text": "explain langgraph routing", "top_k": 50, "hybrid": True, "reranker": True, "rerank_top_k": 10, "metadata_filter": None}}}


# Helper to build query filters
def build_qdrant_filter(metadata_filter: dict[str, Any] | None) -> models.Filter | None:
    must_conditions = []

    # Add user-defined filters
    if metadata_filter:
        for key, value in metadata_filter.items():
            if isinstance(value, dict | list):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Filter value for key '{key}' must be a primitive type (string, integer, float, or boolean), got {type(value).__name__}."
                )
            must_conditions.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))

    if not must_conditions:
        return None
    return models.Filter(must=must_conditions)


@router.post("/retrieve", status_code=status.HTTP_200_OK)
async def retrieve(request: Request, payload: RetrieveRequest):
    try:
        client = request.app.state.qdrant_client

        # Build the metadata filter
        query_filter = build_qdrant_filter(payload.metadata_filter)

        # Dynamically set initial Qdrant limit (larger pool if reranking is enabled)
        search_limit = payload.top_k if payload.reranker else payload.rerank_top_k

        # 1. Generate dense query embedding
        query_vector = await embedder.embed_query(payload.query_text)

        if payload.hybrid:
            # 2a. Execute Hybrid Search (Dense + BM25 Sparse with RRF Fusion)
            response = await client.query_points(
                collection_name=settings.qdrant_collection,
                prefetch=[
                    # Prefetch Dense
                    models.Prefetch(
                        query=query_vector,
                        using="dense_vector",
                        filter=query_filter,
                        limit=search_limit,
                    ),
                    # Prefetch BM25 Sparse (evaluated server-side)
                    models.Prefetch(
                        query=models.Document(text=payload.query_text, model="Qdrant/bm25"),
                        using="bm25_sparse_vector",
                        filter=query_filter,
                        limit=search_limit,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=search_limit,
                with_payload=True,
            )
        else:
            # 2b. Fallback to standard Dense-only Search
            response = await client.query_points(
                collection_name=settings.qdrant_collection,
                query=query_vector,
                using="dense_vector",
                filter=query_filter,
                limit=search_limit,
                with_payload=True,
            )

        # 3. Format results to return to the client
        results = []
        for point in response.points:
            results.append(
                {
                    "chunk_id": point.id,
                    "score": point.score,
                    "text": point.payload.get("text"),
                    "metadata": {
                        "doc_id": point.payload.get("doc_id"),
                        "doc_url": point.payload.get("doc_url"),
                        "chunk_index": point.payload.get("chunk_index"),
                    },
                }
            )

        # 4. Optional: Run Reranker on the results
        if payload.reranker:
            results = await reranker_client.rerank(payload.query_text, results, payload.rerank_top_k)

        return {"results": results}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve documents: {str(e)}",
        ) from e
