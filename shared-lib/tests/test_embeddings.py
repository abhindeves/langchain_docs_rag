import json
from unittest.mock import MagicMock, patch

import pytest

from shared.embeddings import Embedder


@patch("shared.embeddings.boto3.client")
def test_embedder_initialization(mock_boto_client):
    with patch("shared.embeddings.get_shared_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.embedding_model = "amazon.titan-embed-text-v2:0"
        mock_settings.aws_region = "ap-south-1"
        mock_get_settings.return_value = mock_settings

        _ = Embedder()

        # Verify boto3.client called
        mock_boto_client.assert_called_once()
        call_args = mock_boto_client.call_args[1]
        assert call_args["service_name"] == "bedrock-runtime"
        assert call_args["region_name"] == "ap-south-1"
        assert "config" in call_args


@pytest.mark.anyio
@patch("shared.embeddings.boto3.client")
async def test_embed_query(mock_boto_client):
    mock_bedrock = MagicMock()
    mock_boto_client.return_value = mock_bedrock

    # Mock invoke_model response body stream
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps({"embedding": [0.1, 0.2, 0.3]}).encode(
        "utf-8"
    )

    mock_response = {"body": mock_body}
    mock_bedrock.invoke_model.return_value = mock_response

    embedder = Embedder()
    vector = await embedder.embed_query("hello")

    assert vector == [0.1, 0.2, 0.3]
    mock_bedrock.invoke_model.assert_called_once()

    # Check that invoke_model is called with the correct parameters
    call_args = mock_bedrock.invoke_model.call_args[1]
    assert call_args["modelId"] == "amazon.titan-embed-text-v2:0"
    payload = json.loads(call_args["body"])
    assert payload["inputText"] == "hello"


@pytest.mark.anyio
@patch("shared.embeddings.boto3.client")
async def test_embed_documents(mock_boto_client):
    mock_bedrock = MagicMock()
    mock_boto_client.return_value = mock_bedrock

    # Mock invoke_model responses
    mock_body1 = MagicMock()
    mock_body1.read.return_value = json.dumps({"embedding": [0.1, 0.2]}).encode("utf-8")
    mock_body2 = MagicMock()
    mock_body2.read.return_value = json.dumps({"embedding": [0.3, 0.4]}).encode("utf-8")

    mock_bedrock.invoke_model.side_effect = [
        {"body": mock_body1},
        {"body": mock_body2},
    ]

    embedder = Embedder()
    vectors = await embedder.embed_documents(["hello", "world"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert mock_bedrock.invoke_model.call_count == 2

    # Test empty list guard
    assert await embedder.embed_documents([]) == []
