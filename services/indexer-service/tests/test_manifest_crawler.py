import hashlib
import json
from unittest.mock import MagicMock, call, patch

from botocore.exceptions import ClientError
from indexer.manifest_crawler import get_sanitized_name, run_manifest_crawler, settings
from langchain_core.documents import Document


@patch("indexer.manifest_crawler.s3_client")
@patch("indexer.manifest_crawler.update_document_hash")
@patch("indexer.manifest_crawler.parse_raw_docs")
@patch("indexer.manifest_crawler.download_raw_docs")
def test_manifest_crawler_fresh_run(mock_download, mock_parse_docs, mock_update_hash, mock_s3):
    # Arrange: Set up mock documents
    doc1 = Document(page_content="Content 1", metadata={"url": "https://example.com/p1", "title": "Page 1"})
    doc2 = Document(page_content="Content 2", metadata={"url": "https://example.com/p2", "title": "Page 2"})
    mock_parse_docs.return_value = [doc1, doc2]

    # Mock S3 get_object to throw NoSuchKey ClientError (simulating no existing manifest)
    no_key_error = ClientError({"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}}, "GetObject")
    mock_s3.get_object.side_effect = no_key_error

    hash1 = hashlib.md5(b"Content 1").hexdigest()
    hash2 = hashlib.md5(b"Content 2").hexdigest()

    # Act
    target_url = "https://example.com/llms.txt"
    result = run_manifest_crawler(target_url)

    # Assert
    assert result == 2  # Both uploaded

    # Verify both uploads were made to S3
    # Two document uploads + one final manifest.json upload = 3 calls
    # Let's verify the put_object calls
    assert mock_s3.put_object.call_count == 3

    # Verify DynamoDB was marked PENDING for both
    assert mock_update_hash.call_count == 2
    mock_update_hash.assert_has_calls(
        [
            call("https://example.com/p1", hash1, status="PENDING"),
            call("https://example.com/p2", hash2, status="PENDING"),
        ],
        any_order=True,
    )

    # Verify the manifest was uploaded with correct content
    target_url_name = get_sanitized_name(target_url)
    expected_manifest_key = f"manifests/{target_url_name}.json"

    # Grab manifest upload payload
    manifest_call = None
    for c in mock_s3.put_object.call_args_list:
        if c[1].get("Key") == expected_manifest_key:
            manifest_call = c
            break

    assert manifest_call is not None
    uploaded_manifest = json.loads(manifest_call[1]["Body"])

    assert "https://example.com/p1" in uploaded_manifest
    assert uploaded_manifest["https://example.com/p1"]["hash"] == hash1
    assert "https://example.com/p2" in uploaded_manifest
    assert uploaded_manifest["https://example.com/p2"]["hash"] == hash2


@patch("indexer.manifest_crawler.s3_client")
@patch("indexer.manifest_crawler.update_document_hash")
@patch("indexer.manifest_crawler.parse_raw_docs")
@patch("indexer.manifest_crawler.download_raw_docs")
def test_manifest_crawler_no_changes(mock_download, mock_parse_docs, mock_update_hash, mock_s3):
    # Arrange: Set up mock documents matching existing manifest
    doc1 = Document(page_content="Content 1", metadata={"url": "https://example.com/p1", "title": "Page 1"})
    mock_parse_docs.return_value = [doc1]

    hash1 = hashlib.md5(b"Content 1").hexdigest()
    existing_manifest = {"https://example.com/p1": {"hash": hash1, "s3_key": f"raw/pages/{hashlib.md5(b'https://example.com/p1').hexdigest()}.json"}}

    # Mock S3 get_object to return the manifest
    mock_response = {"Body": MagicMock()}
    mock_response["Body"].read.return_value = json.dumps(existing_manifest).encode("utf-8")
    mock_s3.get_object.return_value = mock_response

    # Act
    target_url = "https://example.com/llms.txt"
    result = run_manifest_crawler(target_url)

    # Assert
    assert result == 0  # No files uploaded because hashes matched

    # No document uploads, but the manifest is still saved/updated back to S3
    assert mock_s3.put_object.call_count == 1
    mock_update_hash.assert_not_called()


@patch("indexer.manifest_crawler.s3_client")
@patch("indexer.manifest_crawler.update_document_hash")
@patch("indexer.manifest_crawler.parse_raw_docs")
@patch("indexer.manifest_crawler.download_raw_docs")
def test_manifest_crawler_with_updates(mock_download, mock_parse_docs, mock_update_hash, mock_s3):
    # Arrange: doc1 is unchanged, doc2 is updated
    doc1 = Document(page_content="Content 1", metadata={"url": "https://example.com/p1", "title": "Page 1"})
    doc2 = Document(page_content="Updated Content 2", metadata={"url": "https://example.com/p2", "title": "Page 2"})
    mock_parse_docs.return_value = [doc1, doc2]

    hash1 = hashlib.md5(b"Content 1").hexdigest()
    old_hash2 = hashlib.md5(b"Old Content 2").hexdigest()
    new_hash2 = hashlib.md5(b"Updated Content 2").hexdigest()

    existing_manifest = {"https://example.com/p1": {"hash": hash1, "s3_key": "raw/pages/p1.json"}, "https://example.com/p2": {"hash": old_hash2, "s3_key": "raw/pages/p2.json"}}

    # Mock S3 get_object to return the existing manifest
    mock_response = {"Body": MagicMock()}
    mock_response["Body"].read.return_value = json.dumps(existing_manifest).encode("utf-8")
    mock_s3.get_object.return_value = mock_response

    # Act
    target_url = "https://example.com/llms.txt"
    result = run_manifest_crawler(target_url)

    # Assert
    assert result == 1  # Only doc2 uploaded

    # Only doc2 update_document_hash is called
    mock_update_hash.assert_called_once_with("https://example.com/p2", new_hash2, status="PENDING")

    # Verify manifest was uploaded with updated hash for doc2
    target_url_name = get_sanitized_name(target_url)
    expected_manifest_key = f"manifests/{target_url_name}.json"

    manifest_call = None
    for c in mock_s3.put_object.call_args_list:
        if c[1].get("Key") == expected_manifest_key:
            manifest_call = c
            break

    assert manifest_call is not None
    uploaded_manifest = json.loads(manifest_call[1]["Body"])

    assert uploaded_manifest["https://example.com/p1"]["hash"] == hash1
    assert uploaded_manifest["https://example.com/p2"]["hash"] == new_hash2


@patch("indexer.manifest_crawler.delete_document_vectors")
@patch("indexer.manifest_crawler.get_table")
@patch("indexer.manifest_crawler.s3_client")
@patch("indexer.manifest_crawler.update_document_hash")
@patch("indexer.manifest_crawler.parse_raw_docs")
@patch("indexer.manifest_crawler.download_raw_docs")
def test_manifest_crawler_prune_deleted(mock_download, mock_parse_docs, mock_update_hash, mock_s3, mock_get_table, mock_delete_vectors):
    # Arrange: crawler returns only doc1, doc2 is deleted (stale in manifest)
    doc1 = Document(page_content="Content 1", metadata={"url": "https://example.com/p1", "title": "Page 1"})
    mock_parse_docs.return_value = [doc1]

    hash1 = hashlib.md5(b"Content 1").hexdigest()
    hash2 = hashlib.md5(b"Content 2").hexdigest()

    existing_manifest = {"https://example.com/p1": {"hash": hash1, "s3_key": "raw/pages/p1.json"}, "https://example.com/p2": {"hash": hash2, "s3_key": "raw/pages/p2.json"}}

    # Mock S3 get_object to return the existing manifest
    mock_response = {"Body": MagicMock()}
    mock_response["Body"].read.return_value = json.dumps(existing_manifest).encode("utf-8")
    mock_s3.get_object.return_value = mock_response

    # Mock DynamoDB table deletion call
    mock_table = MagicMock()
    mock_get_table.return_value = mock_table

    # Act
    target_url = "https://example.com/llms.txt"
    result = run_manifest_crawler(target_url)

    # Assert
    assert result == 0  # No updates

    # Verify that orphaned doc2 was deleted
    mock_delete_vectors.assert_called_once_with("https://example.com/p2")
    mock_s3.delete_object.assert_called_once_with(Bucket=settings.s3_bucket, Key="raw/pages/p2.json")
    mock_table.delete_item.assert_called_once_with(Key={"doc_id": "https://example.com/p2"})

    # Verify final manifest no longer contains doc2
    target_url_name = get_sanitized_name(target_url)
    expected_manifest_key = f"manifests/{target_url_name}.json"

    manifest_call = None
    for c in mock_s3.put_object.call_args_list:
        if c[1].get("Key") == expected_manifest_key:
            manifest_call = c
            break

    assert manifest_call is not None
    uploaded_manifest = json.loads(manifest_call[1]["Body"])

    assert "https://example.com/p1" in uploaded_manifest
    assert "https://example.com/p2" not in uploaded_manifest
