from unittest.mock import MagicMock, patch

import pytest

from rag_shared.llm import LLM


@patch("rag_shared.llm.boto3.client")
def test_llm_initialization(mock_boto_client):
    with patch("rag_shared.llm.get_shared_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.chat_model = "anthropic.claude-3-haiku-20240307-v1:0"
        mock_settings.aws_region = "ap-south-1"
        mock_get_settings.return_value = mock_settings

        llm = LLM()

        # Verify boto3.client called
        mock_boto_client.assert_called_once()
        call_args = mock_boto_client.call_args[1]
        assert call_args["service_name"] == "bedrock-runtime"
        assert call_args["region_name"] == "ap-south-1"
        assert "config" in call_args
        assert llm.model == "anthropic.claude-3-haiku-20240307-v1:0"


@pytest.mark.anyio
@patch("rag_shared.llm.boto3.client")
async def test_llm_invoke(mock_boto_client):
    mock_bedrock = MagicMock()
    mock_boto_client.return_value = mock_bedrock

    # Mock converse response structure
    mock_response = {"output": {"message": {"role": "assistant", "content": [{"text": "This is the generated answer from the context."}]}}}
    mock_bedrock.converse.return_value = mock_response

    llm = LLM()
    response = await llm.invoke(query_text="What is the answer?", context="Document context.")

    assert response == "This is the generated answer from the context."
    mock_bedrock.converse.assert_called_once()

    # Verify query parameters
    call_args = mock_bedrock.converse.call_args[1]
    assert call_args["modelId"] == llm.model
    assert len(call_args["system"]) == 1
    assert "strictly based on the provided document context" in call_args["system"][0]["text"]
    assert len(call_args["messages"]) == 1
    assert call_args["messages"][0]["role"] == "user"
    assert "Context:\nDocument context." in call_args["messages"][0]["content"][0]["text"]
    assert "Query: What is the answer?" in call_args["messages"][0]["content"][0]["text"]
