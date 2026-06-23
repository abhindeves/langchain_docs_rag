import json
from unittest.mock import AsyncMock, MagicMock, patch

# Patch boto3 before importing lambda_handler to avoid real AWS configuration calls
with patch("boto3.client"), patch("boto3.resource"):
    from indexer.lambda_handler import crawl_handler, embedder, worker_handler


@patch("indexer.lambda_handler.run_crawler")
def test_crawl_handler(mock_run_crawler):
    # Arrange
    mock_run_crawler.return_value = 42

    # Act
    response = crawl_handler({}, None)

    # Assert
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "Crawl executed successfully"
    assert body["jobs_dispatched"] == 42
    mock_run_crawler.assert_called_once()


@patch("indexer.lambda_handler.download_from_s3")
@patch("indexer.lambda_handler.parse_raw_docs")
@patch("indexer.lambda_handler.check_document_hash")
@patch("indexer.lambda_handler.chunk_markdown_docs")
@patch("indexer.lambda_handler.save_chunks_to_qdrant")
@patch("indexer.lambda_handler.update_document_hash")
def test_worker_handler_success(
    mock_update_hash,
    mock_save_qdrant,
    mock_chunk_docs,
    mock_check_hash,
    mock_parse_docs,
    mock_download_s3,
):
    # Arrange
    record_body = {
        "s3_bucket": "test-bucket",
        "s3_key": "raw/pages/some-hash.txt",
        "doc_id": "https://example.com/doc1",
        "doc_url": "https://example.com/doc1",
        "title": "Header 1",
        "hash": "old-hash",
    }
    event = {"Records": [{"body": json.dumps(record_body), "messageId": "msg-12345"}]}

    mock_download_s3.return_value = "raw file text from S3"

    # Create mock Documents
    mock_doc = MagicMock()
    mock_doc.metadata = {"url": "https://example.com/doc1"}
    mock_doc.page_content = "doc content text"
    mock_parse_docs.return_value = [mock_doc]

    mock_check_hash.return_value = False  # Changed/New content

    mock_chunk = MagicMock()
    mock_chunk.page_content = "chunk content"
    mock_chunk_docs.return_value = [mock_chunk]

    # Mock the async embeddings call
    embedder.embed_documents = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    # Act
    response = worker_handler(event, None)

    # Assert
    assert response["statusCode"] == 200
    assert "Batch processed successfully" in response["body"]

    # Verify processing pipeline steps
    mock_download_s3.assert_called_once_with("test-bucket", "raw/pages/some-hash.txt")
    mock_parse_docs.assert_called_once_with("raw file text from S3")
    mock_check_hash.assert_called_once()
    mock_chunk_docs.assert_called_once_with([mock_doc])
    embedder.embed_documents.assert_called_once_with(["chunk content"])
    mock_save_qdrant.assert_called_once_with(
        "https://example.com/doc1",
        "https://example.com/doc1",
        ["chunk content"],
        [[0.1, 0.2, 0.3]],
    )
    mock_update_hash.assert_called_once()


@patch("indexer.lambda_handler.download_from_s3")
def test_worker_handler_failure(mock_download_s3):
    # Arrange
    event = {
        "Records": [
            {
                "body": json.dumps({"s3_bucket": "test-bucket", "s3_key": "some-key"}),
                "messageId": "msg-failure",
            }
        ]
    }
    mock_download_s3.side_effect = RuntimeError("S3 Download failed!")

    # Act & Assert
    import pytest

    with pytest.raises(RuntimeError, match="S3 Download failed!"):
        worker_handler(event, None)
