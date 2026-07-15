import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from rag_shared.embeddings import Embedder

router = APIRouter()
embedder = Embedder()


class EmbedRequest(BaseModel):
    text: str = Field(..., description="The text to generate embeddings for.")


@router.post("/embed", status_code=status.HTTP_200_OK)
async def embed_function(request: EmbedRequest):
    """Embed text and return the embedding vector."""
    try:
        vector = await embedder.embed_query(request.text)
        return {"embedding": vector}
    except Exception as e:
        logging.error(f"Failed to embed text: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to embed text: {str(e)}",
        ) from e
