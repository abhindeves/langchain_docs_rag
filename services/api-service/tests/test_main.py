from unittest.mock import AsyncMock, MagicMock, patch

from api.main import app
from fastapi.testclient import TestClient


def test_liveness():
    """Verify that the liveness check returns HTTP 200."""
    with TestClient(app) as client:
        response = client.get("/health/liveness")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "api-service"}


@patch("api.main.settings")
@patch("api.main.AsyncQdrantClient")
def test_readiness_success(mock_qdrant_client_class, mock_settings):
    """Verify that readiness check succeeds when AsyncQdrantClient list collections responds."""
    # Configure mock settings
    mock_settings.qdrant_host = "http://mock-qdrant"
    mock_settings.qdrant_api_key = "mock-key"

    # Mock the instance returned by AsyncQdrantClient
    mock_client_instance = MagicMock()
    mock_qdrant_client_class.return_value = mock_client_instance

    # Mock get_collections and close to succeed as coroutines (using AsyncMock)
    mock_client_instance.get_collections = AsyncMock(return_value=[])
    mock_client_instance.close = AsyncMock()

    # We must use TestClient in a context manager to execute lifespan startup events
    with TestClient(app) as client:
        response = client.get("/health/readiness")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "database": "connected"}

    # Verify instantiation and async method call
    mock_qdrant_client_class.assert_called_once_with(
        url="http://mock-qdrant",
        api_key="mock-key",
    )
    mock_client_instance.get_collections.assert_called_once()
    mock_client_instance.close.assert_called_once()


@patch("api.main.settings")
@patch("api.main.AsyncQdrantClient")
def test_readiness_failure(mock_qdrant_client_class, mock_settings):
    """Verify that readiness check returns 503 Service Unavailable on Qdrant exceptions."""
    # Configure mock settings
    mock_settings.qdrant_host = "http://mock-qdrant"
    mock_settings.qdrant_api_key = "mock-key"

    # Mock the instance returned by AsyncQdrantClient
    mock_client_instance = MagicMock()
    mock_qdrant_client_class.return_value = mock_client_instance

    # Mock get_collections and close to handle async calls
    mock_client_instance.get_collections = AsyncMock(side_effect=Exception("Connection refused"))
    mock_client_instance.close = AsyncMock()

    with TestClient(app) as client:
        response = client.get("/health/readiness")
        assert response.status_code == 503
        assert "Qdrant database is not reachable" in response.json()["detail"]

    # Verify instantiation and async method call
    mock_qdrant_client_class.assert_called_once_with(
        url="http://mock-qdrant",
        api_key="mock-key",
    )
    mock_client_instance.get_collections.assert_called_once()
    mock_client_instance.close.assert_called_once()
