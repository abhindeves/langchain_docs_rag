from unittest.mock import MagicMock, patch

from indexer.storage import check_document_hash, update_document_hash


@patch("indexer.storage.dynamodb")
def test_check_document_hash(mock_dynamodb):
    # Arrange: Mock DynamoDB Table lookup
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {"content_hash": "correcthash", "status": "COMPLETED"}
    }

    # Act & Assert
    assert check_document_hash("doc1", "correcthash") is True
    assert check_document_hash("doc1", "wronghash") is False

    # Verify key was requested correctly
    mock_table.get_item.assert_called_with(Key={"doc_id": "doc1"})


@patch("indexer.storage.dynamodb")
def test_update_document_hash(mock_dynamodb):
    # Arrange: Mock DynamoDB Table
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    # Act: Update hash
    update_document_hash("doc1", "newhash")

    # Assert: Verify PutItem parameters
    mock_table.put_item.assert_called_once_with(
        Item={"doc_id": "doc1", "content_hash": "newhash", "status": "COMPLETED"}
    )
