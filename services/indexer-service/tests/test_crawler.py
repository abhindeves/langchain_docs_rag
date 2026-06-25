import hashlib
import json
from unittest.mock import patch

from indexer.crawler import run_crawler

from rag_shared.config import get_shared_settings


@patch("indexer.crawler.s3_client")
@patch("indexer.crawler.sqs_client")
@patch("indexer.crawler.check_document_hash")
@patch("indexer.crawler.update_document_hash")
@patch("indexer.crawler.download_raw_docs")
def test_run_crawler(
    mock_download, mock_update_hash, mock_check_hash, mock_sqs, mock_s3
):
    # Arrange: Set up mock return values
    mock_download.return_value = (
        "# Header 1\nSource: https://example.com/doc1\nThis is mock content for page 1."
    )
    mock_check_hash.return_value = False  # Force processing
    settings = get_shared_settings()

    doc_url = "https://example.com/doc1"
    expected_s3_key = (
        f"raw/pages/{hashlib.md5(doc_url.encode('utf-8')).hexdigest()}.txt"
    )
    expected_content = (
        "# Header 1\nSource: https://example.com/doc1\nThis is mock content for page 1."
    )

    # Act: Execute crawler
    result = run_crawler()

    # Assert: Verify response and client arguments
    assert result == 1

    # Verify S3 client was called correctly
    mock_s3.put_object.assert_called_once_with(
        Bucket=settings.s3_bucket, Key=expected_s3_key, Body=expected_content
    )

    # Verify SQS client was called correctly
    mock_sqs.send_message.assert_called_once()
    _, kwargs = mock_sqs.send_message.call_args
    assert kwargs["QueueUrl"] == settings.sqs_queue_url

    # Validate SQS Message payload format
    payload = json.loads(kwargs["MessageBody"])
    assert payload["s3_bucket"] == settings.s3_bucket
    assert payload["s3_key"] == expected_s3_key
    assert payload["doc_id"] == doc_url
    assert payload["doc_url"] == doc_url
    assert payload["title"] == "Header 1"

    # Verify DynamoDB status was marked PENDING
    mock_update_hash.assert_called_once_with(
        doc_url,
        hashlib.md5(expected_content.encode("utf-8")).hexdigest(),
        status="PENDING",
    )
