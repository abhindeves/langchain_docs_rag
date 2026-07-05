from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from indexer.storage import check_document_hash, save_chunks_to_qdrant, update_document_hash


@patch("indexer.storage.dynamodb")
def test_check_document_hash(mock_dynamodb):
    # Arrange: Mock DynamoDB Table lookup
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.get_item.return_value = {"Item": {"content_hash": "correcthash", "status": "COMPLETED"}}

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
    mock_table.put_item.assert_called_once_with(Item={"doc_id": "doc1", "content_hash": "newhash", "status": "COMPLETED"})


@pytest.mark.anyio
@patch("indexer.storage.delete_document_vectors")
@patch("indexer.storage.get_qdrant_client")
@patch("indexer.storage.embedder")
async def test_save_chunks_to_qdrant(mock_embedder, mock_get_client, mock_delete_vectors):
    # Arrange
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True
    mock_get_client.return_value = mock_client

    mock_embedder.embed_documents = AsyncMock(return_value=[[0.1] * 1024])

    # Act
    await save_chunks_to_qdrant(doc_id="doc1", doc_url="https://example.com/doc1", chunks=["chunk content"])

    # Assert
    mock_delete_vectors.assert_called_once_with("doc1")
    mock_client.upsert.assert_called_once()

    # Verify the upserted point contains Document(text="chunk content", model="Qdrant/bm25")
    upsert_args = mock_client.upsert.call_args[1]
    points = upsert_args["points"]
    assert len(points) == 1
    point = points[0]

    from qdrant_client.models import Document, PointStruct

    assert isinstance(point, PointStruct)
    assert point.vector["dense_vector"] == [0.1] * 1024

    sparse_doc = point.vector["bm25_sparse_vector"]
    assert isinstance(sparse_doc, Document)
    assert sparse_doc.text == "chunk content"
    assert sparse_doc.model == "Qdrant/bm25"
    assert point.payload["doc_id"] == "doc1"
