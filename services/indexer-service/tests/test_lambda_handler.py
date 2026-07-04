import json
from unittest.mock import AsyncMock, MagicMock, call, patch

# Patch boto3 before importing lambda_handler to avoid real AWS configuration calls
with patch("boto3.client"), patch("boto3.resource"):
    from indexer.lambda_handler import crawl_handler, master_crawl_handler, worker_handler


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
@patch("indexer.lambda_handler.save_chunks_to_qdrant", new_callable=AsyncMock)
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

    mock_save_qdrant.assert_called_once_with(
        "https://example.com/doc1",
        "https://example.com/doc1",
        ["chunk content"],
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


@patch("os.environ", {"CRAWLER_QUEUE_URL": "https://sqs.ap-south-1.amazonaws.com/12345/test-queue", "TARGET_URLS": "https://example.com/doc1,https://example.com/doc2"})
@patch("boto3.client")
def test_master_crawl_handler(mock_boto_client):
    # Arrange
    mock_sqs = MagicMock()
    mock_boto_client.return_value = mock_sqs

    # Act
    response = master_crawl_handler({}, None)

    # Assert
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "Dispatched 2/2 jobs" in body["message"]
    assert body["dispatched_count"] == 2

    # Verify SQS send_message calls
    assert mock_sqs.send_message.call_count == 2
    mock_sqs.send_message.assert_has_calls(
        [
            call(
                QueueUrl="https://sqs.ap-south-1.amazonaws.com/12345/test-queue",
                MessageBody=json.dumps({"target_url": "https://example.com/doc1"}),
            ),
            call(
                QueueUrl="https://sqs.ap-south-1.amazonaws.com/12345/test-queue",
                MessageBody=json.dumps({"target_url": "https://example.com/doc2"}),
            ),
        ],
        any_order=True,
    )


@patch("os.environ", {"CRAWLER_QUEUE_URL": "https://sqs.ap-south-1.amazonaws.com/12345/test-queue", "TARGET_URLS": "https://example.com/doc1"})
@patch("boto3.client")
def test_master_crawl_handler_event_override(mock_boto_client):
    # Arrange
    mock_sqs = MagicMock()
    mock_boto_client.return_value = mock_sqs

    # Act
    event = {"target_urls": "https://example.com/doc_override"}
    response = master_crawl_handler(event, None)

    # Assert
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "Dispatched 1/1 jobs" in body["message"]
    assert body["dispatched_count"] == 1

    # Verify SQS send_message called with overridden URL
    mock_sqs.send_message.assert_called_once_with(
        QueueUrl="https://sqs.ap-south-1.amazonaws.com/12345/test-queue",
        MessageBody=json.dumps({"target_url": "https://example.com/doc_override"}),
    )
