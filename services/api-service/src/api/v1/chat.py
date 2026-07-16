import logging
from typing import Any

from api.config import get_api_settings
from api.v1.retrieval import build_qdrant_filter, retrieve_result
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from rag_shared.embeddings import Embedder
from rag_shared.llm import LLM
from rag_shared.reranker import Reranker

router = APIRouter()
settings = get_api_settings()
embedder = Embedder()
reranker = Reranker()
llm = LLM()


class ChatRequest(BaseModel):
    query_text: str = Field(..., description="The query text to retrieve documents for.")
    top_k: int = Field(default=50, description="The number of documents to retrieve.")
    hybrid: bool = Field(default=True, description="whether to use hybrid search.")
    reranker: bool = Field(default=True, description="Whether to use reranker.")
    rerank_top_k: int = Field(default=10, description="The number of documents to rerank.")
    metadata_filter: dict[str, Any] | None = Field(default=None, description="Metadata filter to apply to the search.")


@router.post("/chat", status_code=status.HTTP_200_OK)
async def chat(request: Request, payload: ChatRequest):
    try:
        # get the qdrant client
        qdrant_client = request.app.state.qdrant_client

        # get the query text
        query_text = payload.query_text

        # use the embedder to get the query vector
        query_vector = await embedder.embed_query(query_text)

        # build metadata filter
        query_filter = build_qdrant_filter(payload.metadata_filter)

        # number of documents to retrieve from Qdrant
        search_limit = payload.top_k

        # use the retriever
        retrieved_documents = await retrieve_result(
            client=qdrant_client, query_filter=query_filter, search_limit=search_limit, query_vector=query_vector, hybrid=payload.hybrid, query_text=payload.query_text
        )

        # use the reranker to rerank the retrieved documents
        if payload.reranker:
            retrieved_documents = await reranker.rerank(query_text, retrieved_documents, payload.rerank_top_k)

        # join the docs for context
        context = "\n\n".join([doc["text"] for doc in retrieved_documents])

        # get the llm
        response = await llm.invoke(query_text, context)

        return {"response": response, "sources": retrieved_documents}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to generate chat response: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chat response: {str(e)}",
        ) from e
