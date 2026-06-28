from unittest.mock import MagicMock, patch

from api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_liveness():
    response = client.get("/health/liveness")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api-service"}


@patch("api.main.settings")
@patch("api.main.QdrantClient")
def test_readiness_success(mock_qdrant_client_class, mock_settings):
    # Configure mock settings
    mock_settings.qdrant_host = "http://mock-qdrant"
    mock_settings.qdrant_api_key = "mock-key"

    # Mock the instance returned by QdrantClient
    mock_client_instance = MagicMock()
    mock_qdrant_client_class.return_value = mock_client_instance

    # Mock get_collections to succeed
    mock_client_instance.get_collections.return_value = []

    response = client.get("/health/readiness")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}

    # Verify instantiation and method call
    mock_qdrant_client_class.assert_called_once_with(
        url="http://mock-qdrant",
        api_key="mock-key",
        timeout=2,
    )
    mock_client_instance.get_collections.assert_called_once()


@patch("api.main.settings")
@patch("api.main.QdrantClient")
def test_readiness_failure(mock_qdrant_client_class, mock_settings):
    # Configure mock settings
    mock_settings.qdrant_host = "http://mock-qdrant"
    mock_settings.qdrant_api_key = "mock-key"

    # Mock the instance returned by QdrantClient to raise an exception
    mock_client_instance = MagicMock()
    mock_qdrant_client_class.return_value = mock_client_instance

    mock_client_instance.get_collections.side_effect = Exception("Connection refused")

    response = client.get("/health/readiness")
    assert response.status_code == 503
    assert "Qdrant database is not reachable" in response.json()["detail"]

    # Verify instantiation and method call
    mock_qdrant_client_class.assert_called_once_with(
        url="http://mock-qdrant",
        api_key="mock-key",
        timeout=2,
    )
    mock_client_instance.get_collections.assert_called_once()
