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
@patch("indexer.lambda_handler.check_document_hash")
@patch("indexer.lambda_handler.chunk_markdown_docs")
@patch("indexer.lambda_handler.save_chunks_to_qdrant")
@patch("indexer.lambda_handler.update_document_hash")
def test_worker_handler_success(
    mock_update_hash,
    mock_save_qdrant,
    mock_chunk_docs,
    mock_check_hash,
    mock_download_s3,
):
    # Arrange: Native S3 Event Notification format inside SQS message body
    s3_event_body = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "raw/pages/some-hash.json"},
                }
            }
        ]
    }
    event = {
        "Records": [
            {
                "body": json.dumps(s3_event_body),
                "messageId": "msg-12345",
                "attributes": {"ApproximateReceiveCount": "1"},
            }
        ]
    }

    # S3 returns serialized JSON content
    mock_download_s3.return_value = json.dumps(
        {
            "doc_id": "https://example.com/doc1",
            "doc_url": "https://example.com/doc1",
            "title": "Header 1",
            "hash": "old-hash",
            "page_content": "doc content text",
        }
    )

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
    mock_download_s3.assert_called_once_with("test-bucket", "raw/pages/some-hash.json")
    mock_check_hash.assert_called_once_with("https://example.com/doc1", "old-hash")

    # Check that chunk_markdown_docs was called with a Document object reconstructed from JSON
    mock_chunk_docs.assert_called_once()
    reconstructed_doc = mock_chunk_docs.call_args[0][0][0]
    assert reconstructed_doc.page_content == "doc content text"
    assert reconstructed_doc.metadata["url"] == "https://example.com/doc1"
    assert reconstructed_doc.metadata["title"] == "Header 1"

    embedder.embed_documents.assert_called_once_with(["chunk content"])
    mock_save_qdrant.assert_called_once_with(
        "https://example.com/doc1",
        "https://example.com/doc1",
        ["chunk content"],
        [[0.1, 0.2, 0.3]],
    )
    mock_update_hash.assert_called_once_with("https://example.com/doc1", "old-hash")


@patch("indexer.lambda_handler.download_from_s3")
@patch("indexer.lambda_handler.update_document_hash")
def test_worker_handler_retry_exhaustion_failure(mock_update_hash, mock_download_s3):
    # Arrange: SQS message has ApproximateReceiveCount = 3
    s3_event_body = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "raw/pages/some-hash.json"},
                }
            }
        ]
    }
    event = {
        "Records": [
            {
                "body": json.dumps(s3_event_body),
                "messageId": "msg-failure",
                "attributes": {"ApproximateReceiveCount": "3"},
            }
        ]
    }

    # S3 download succeeds but processing (e.g. Qdrant or Embeddings) fails
    mock_download_s3.return_value = json.dumps(
        {
            "doc_id": "https://example.com/doc1",
            "doc_url": "https://example.com/doc1",
            "title": "Header 1",
            "hash": "old-hash",
            "page_content": "doc content text",
        }
    )

    # Force an exception inside processing by patching check_document_hash to fail
    with patch(
        "indexer.lambda_handler.check_document_hash",
        side_effect=RuntimeError("Qdrant write failed!"),
    ):
        # Act & Assert
        import pytest

        with pytest.raises(RuntimeError, match="Qdrant write failed!"):
            worker_handler(event, None)

    # Verify status in DynamoDB was updated to FAILED because count was >= 3
    mock_update_hash.assert_called_once_with(
        "https://example.com/doc1",
        "old-hash",
        status="FAILED",
    )
