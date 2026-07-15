from unittest.mock import AsyncMock, patch

from api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@patch("api.v1.embeddings.embedder")
def test_embed_success(mock_embedder):
    """Verify that the /embed endpoint returns the correct embedding vector."""
    mock_embedder.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])

    payload = {"text": "Hello world"}
    response = client.post("/api/v1/embed", json=payload)

    assert response.status_code == 200
    assert response.json() == {"embedding": [0.1, 0.2, 0.3]}
    mock_embedder.embed_query.assert_called_once_with("Hello world")
