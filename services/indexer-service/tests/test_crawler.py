import hashlib
from unittest.mock import call, patch

import pytest
from indexer.crawler import run_crawler
from langchain_core.documents import Document


@patch("indexer.crawler.s3_client")
@patch("indexer.crawler.check_document_hashes_batch")
@patch("indexer.crawler.update_document_hash")
@patch("indexer.crawler.parse_raw_docs")
@patch("indexer.crawler.download_raw_docs")
@patch("indexer.crawler._prune_deleted_documents")
def test_run_crawler_multiple_changes(mock_prune, mock_download, mock_parse_docs, mock_update_hash, mock_check_hash, mock_s3):
    # Arrange: Set up mock documents
    doc1 = Document(page_content="Content 1", metadata={"url": "https://example.com/p1"})
    doc2 = Document(page_content="Content 2", metadata={"url": "https://example.com/p2"})
    mock_parse_docs.return_value = [doc1, doc2]
    mock_check_hash.return_value = set()  # Empty set = no docs are skipped
    mock_prune.return_value = 0

    hash1 = hashlib.md5(b"Content 1").hexdigest()
    hash2 = hashlib.md5(b"Content 2").hexdigest()

    # Act
    result = run_crawler()

    # Assert
    assert result == 2

    # Verify both uploads were made to S3
    assert mock_s3.put_object.call_count == 2

    # Verify DynamoDB was marked PENDING for both
    assert mock_update_hash.call_count == 2
    mock_update_hash.assert_has_calls(
        [
            call("https://example.com/p1", hash1, status="PENDING"),
            call("https://example.com/p2", hash2, status="PENDING"),
        ],
        any_order=True,
    )
    mock_prune.assert_called_once_with({"https://example.com/p1", "https://example.com/p2"})


@patch("indexer.crawler.s3_client")
@patch("indexer.crawler.check_document_hashes_batch")
@patch("indexer.crawler.update_document_hash")
@patch("indexer.crawler.parse_raw_docs")
@patch("indexer.crawler.download_raw_docs")
@patch("indexer.crawler._prune_deleted_documents")
def test_run_crawler_deduplication(mock_prune, mock_download, mock_parse_docs, mock_update_hash, mock_check_hash, mock_s3):
    # Arrange: Page 1 is unchanged, Page 2 is new/changed
    doc1 = Document(page_content="Content 1", metadata={"url": "https://example.com/p1"})
    doc2 = Document(page_content="Content 2", metadata={"url": "https://example.com/p2"})
    mock_parse_docs.return_value = [doc1, doc2]
    mock_prune.return_value = 0

    # Mark Page 1 as unchanged in the mocked batch results
    mock_check_hash.return_value = {"https://example.com/p1"}

    hash2 = hashlib.md5(b"Content 2").hexdigest()

    # Act
    result = run_crawler()

    # Assert
    assert result == 1

    # Only Page 2 should be uploaded to S3
    mock_s3.put_object.assert_called_once()
    _, kwargs = mock_s3.put_object.call_args
    expected_s3_key = f"raw/pages/{hashlib.md5(b'https://example.com/p2').hexdigest()}.json"
    assert kwargs["Key"] == expected_s3_key

    # Only Page 2 should be marked PENDING
    mock_update_hash.assert_called_once_with("https://example.com/p2", hash2, status="PENDING")
    mock_prune.assert_called_once_with({"https://example.com/p1", "https://example.com/p2"})


@patch("indexer.crawler.s3_client")
@patch("indexer.crawler.check_document_hashes_batch")
@patch("indexer.crawler.update_document_hash")
@patch("indexer.crawler.parse_raw_docs")
@patch("indexer.crawler.download_raw_docs")
@patch("indexer.crawler._prune_deleted_documents")
def test_run_crawler_exception_propagation(mock_prune, mock_download, mock_parse_docs, mock_update_hash, mock_check_hash, mock_s3):
    # Arrange: S3 client throws error when put_object is called
    doc1 = Document(page_content="Content 1", metadata={"url": "https://example.com/p1"})
    mock_parse_docs.return_value = [doc1]
    mock_check_hash.return_value = set()
    mock_s3.put_object.side_effect = RuntimeError("S3 PutObject Failed!")
    mock_prune.return_value = 0

    # Act & Assert: Exception is propagated back to the main thread
    with pytest.raises(RuntimeError, match="S3 PutObject Failed!"):
        run_crawler()
