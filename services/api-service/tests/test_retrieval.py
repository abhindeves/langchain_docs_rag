from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from api.main import app
from api.v1.retrieval import retrieve_result
from fastapi.testclient import TestClient
from qdrant_client import models


@patch("api.main.AsyncQdrantClient")
@patch("api.v1.retrieval.embedder")
@patch("api.v1.retrieval.reranker_client")
def test_retrieve_dense_only(mock_reranker, mock_embedder, mock_qdrant_class):
    """Verify retrieval works with dense-only vector search and no reranking."""
    # 1. Mock Bedrock query embedding
    mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)

    # 2. Mock Qdrant client search points response
    mock_qdrant = MagicMock()
    mock_qdrant.query_points = AsyncMock()
    mock_qdrant.close = AsyncMock()

    mock_point = MagicMock()
    mock_point.id = "chunk-1"
    mock_point.score = 0.95
    mock_point.payload = {"text": "This is a document chunk about FastAPI RAG.", "doc_id": "doc-abc", "doc_url": "https://example.com/doc", "chunk_index": 0}

    mock_qdrant.query_points.return_value.points = [mock_point]

    with TestClient(app) as client:
        # Override the qdrant_client in app.state with our mock
        app.state.qdrant_client = mock_qdrant

        payload = {"query_text": "How to deploy FastAPI?", "top_k": 5, "hybrid": False, "reranker": False, "rerank_top_k": 3}

        response = client.post("/api/v1/retrieve", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["chunk_id"] == "chunk-1"
        assert data["results"][0]["score"] == 0.95
        assert data["results"][0]["text"] == "This is a document chunk about FastAPI RAG."

        # Verify calls
        mock_embedder.embed_query.assert_called_once_with("How to deploy FastAPI?")
        mock_qdrant.query_points.assert_called_once()
        mock_reranker.rerank.assert_not_called()


@patch("api.main.AsyncQdrantClient")
@patch("api.v1.retrieval.embedder")
@patch("api.v1.retrieval.reranker_client")
def test_retrieve_hybrid_with_rerank(mock_reranker, mock_embedder, mock_qdrant_class):
    """Verify hybrid search query with second-stage Bedrock reranker."""
    mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)

    mock_qdrant = MagicMock()
    mock_qdrant.query_points = AsyncMock()
    mock_qdrant.close = AsyncMock()

    mock_point = MagicMock()
    mock_point.id = "chunk-2"
    mock_point.score = 0.8
    mock_point.payload = {"text": "Lexical match text block.", "doc_id": "doc-xyz", "doc_url": "https://example.com/lex", "chunk_index": 1}
    mock_qdrant.query_points.return_value.points = [mock_point]

    # Mock Reranker output
    mock_reranker.rerank = AsyncMock(
        return_value=[{"chunk_id": "chunk-2", "score": 0.99, "text": "Lexical match text block.", "metadata": {"doc_id": "doc-xyz", "doc_url": "https://example.com/lex", "chunk_index": 1}}]
    )

    with TestClient(app) as client:
        app.state.qdrant_client = mock_qdrant

        payload = {"query_text": "Hybrid search terms", "top_k": 10, "hybrid": True, "reranker": True, "rerank_top_k": 2}

        response = client.post("/api/v1/retrieve", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["score"] == 0.99

        mock_reranker.rerank.assert_called_once()


@patch("api.main.AsyncQdrantClient")
@patch("api.v1.retrieval.embedder")
@patch("api.v1.retrieval.reranker_client")
def test_retrieve_invalid_filter_type(mock_reranker, mock_embedder, mock_qdrant_class):
    """Verify that using non-primitive types in metadata_filter returns HTTP 400."""
    mock_qdrant = MagicMock()
    mock_qdrant.close = AsyncMock()

    with TestClient(app) as client:
        app.state.qdrant_client = mock_qdrant

        payload = {"query_text": "testing invalid filters", "metadata_filter": {"invalid_field": {"nested": "value"}}}
        response = client.post("/api/v1/retrieve", json=payload)

        assert response.status_code == 400
        assert "must be a primitive type" in response.json()["detail"]


@patch("api.main.AsyncQdrantClient")
@patch("api.v1.retrieval.embedder")
@patch("api.v1.retrieval.reranker_client")
def test_retrieve_uses_top_k_for_qdrant_limit(mock_reranker, mock_embedder, mock_qdrant_class):
    """Verify that the search_limit passed to Qdrant is strictly payload.top_k."""
    mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 1024)
    mock_reranker.rerank = AsyncMock(return_value=[])

    mock_qdrant = MagicMock()
    mock_qdrant.query_points = AsyncMock()
    mock_qdrant.close = AsyncMock()
    mock_qdrant.query_points.return_value.points = []

    with TestClient(app) as client:
        app.state.qdrant_client = mock_qdrant

        # Set top_k to 50, rerank_top_k to 10. We expect limit=50.
        payload = {"query_text": "Test Qdrant limit", "top_k": 50, "hybrid": False, "reranker": True, "rerank_top_k": 10}

        response = client.post("/api/v1/retrieve", json=payload)

        assert response.status_code == 200

        # Verify limit argument to query_points was top_k (50)
        mock_qdrant.query_points.assert_called_once()
        _, kwargs = mock_qdrant.query_points.call_args
        assert kwargs.get("limit") == 50


@pytest.mark.anyio
async def test_retrieve_result_hybrid_direct():
    """Verify retrieve_result direct behavior for hybrid search."""
    mock_client = MagicMock()
    mock_client.query_points = AsyncMock()

    mock_point = MagicMock()
    mock_point.id = "point-123"
    mock_point.score = 0.88
    mock_point.payload = {
        "text": "Target text chunk.",
        "doc_id": "doc-456",
        "doc_url": "https://example.com/doc456",
        "chunk_index": 2,
    }
    mock_client.query_points.return_value.points = [mock_point]

    query_filter = models.Filter(must=[models.FieldCondition(key="category", match=models.MatchValue(value="test"))])
    query_vector = [0.2] * 1024

    results = await retrieve_result(
        client=mock_client,
        query_filter=query_filter,
        search_limit=5,
        query_vector=query_vector,
        hybrid=True,
        query_text="Hybrid query content",
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == "point-123"
    assert results[0]["score"] == 0.88
    assert results[0]["text"] == "Target text chunk."
    assert results[0]["metadata"]["doc_id"] == "doc-456"

    mock_client.query_points.assert_called_once()
    _, kwargs = mock_client.query_points.call_args
    assert kwargs["limit"] == 5
    assert kwargs["with_payload"] is True
    assert isinstance(kwargs["query"], models.FusionQuery)
    assert len(kwargs["prefetch"]) == 2


@pytest.mark.anyio
async def test_retrieve_result_dense_direct():
    """Verify retrieve_result direct behavior for dense-only search."""
    mock_client = MagicMock()
    mock_client.query_points = AsyncMock()
    mock_client.query_points.return_value.points = []

    query_vector = [0.3] * 1024

    results = await retrieve_result(
        client=mock_client,
        query_filter=None,
        search_limit=10,
        query_vector=query_vector,
        hybrid=False,
        query_text="Dense-only query",
    )

    assert len(results) == 0

    mock_client.query_points.assert_called_once()
    _, kwargs = mock_client.query_points.call_args
    assert kwargs["limit"] == 10
    assert kwargs["query"] == query_vector
    assert "prefetch" not in kwargs
