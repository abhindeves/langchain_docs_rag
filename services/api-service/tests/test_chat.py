from unittest.mock import AsyncMock, MagicMock, patch

from api.main import app
from fastapi.testclient import TestClient


@patch("api.main.AsyncQdrantClient")
@patch("api.v1.chat.embedder")
@patch("api.v1.chat.reranker")
@patch("api.v1.chat.llm")
def test_chat_success(mock_llm, mock_reranker, mock_embedder, mock_qdrant_class):
    """Verify that chat endpoint successfully retrieves docs, reranks, and gets response from LLM."""
    mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)

    mock_qdrant = MagicMock()
    mock_qdrant.query_points = AsyncMock()
    mock_qdrant.close = AsyncMock()

    mock_point = MagicMock()
    mock_point.id = "chunk-1"
    mock_point.score = 0.95
    mock_point.payload = {"text": "This is a document chunk about FastAPI RAG.", "doc_id": "doc-abc", "doc_url": "https://example.com/doc", "chunk_index": 0}
    mock_qdrant.query_points.return_value.points = [mock_point]

    mock_reranker.rerank = AsyncMock(
        return_value=[
            {"chunk_id": "chunk-1", "score": 0.95, "text": "This is a document chunk about FastAPI RAG.", "metadata": {"doc_id": "doc-abc", "doc_url": "https://example.com/doc", "chunk_index": 0}}
        ]
    )

    mock_llm.invoke = AsyncMock(return_value="FastAPI RAG is cool.")

    with TestClient(app) as client:
        app.state.qdrant_client = mock_qdrant

        payload = {"query_text": "Tell me about FastAPI RAG", "top_k": 5, "hybrid": False, "reranker": True, "rerank_top_k": 3}

        response = client.post("/api/v1/chat", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "sources" in data
        assert data["response"] == "FastAPI RAG is cool."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["chunk_id"] == "chunk-1"

        # Verify downstream mocks
        mock_embedder.embed_query.assert_called_once_with("Tell me about FastAPI RAG")
        mock_reranker.rerank.assert_called_once()
        mock_llm.invoke.assert_called_once_with("Tell me about FastAPI RAG", "This is a document chunk about FastAPI RAG.")
