import uuid
from typing import Any

import boto3
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from rag_shared.config import get_shared_settings

# Initialize clients using shared settings config
settings = get_shared_settings()
dynamodb: Any = boto3.resource("dynamodb", region_name=settings.aws_region)

TABLE_NAME = "DocumentSyncStatus"


def get_qdrant_client() -> QdrantClient:
    """
    Initializes and returns a Qdrant client connection.
    """
    return QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )


def get_table():
    """
    Retrieves the DynamoDB table instance. Bootstraps
    table creation if it doesn't exist.
    """
    try:
        table = dynamodb.Table(TABLE_NAME)
        table.load()  # Will trigger exception if table does not exist
        return table
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        print(f"DynamoDB Table '{TABLE_NAME}' not found. Creating...")
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "doc_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "doc_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName=TABLE_NAME)
        print(f"Created DynamoDB Table '{TABLE_NAME}'.")
        return table


def check_document_hash(doc_id: str, new_hash: str) -> bool:
    """
    Checks the document hash in DynamoDB.

    Args:
        doc_id (str): The unique identifier of the document.
        new_hash (str): The computed MD5/SHA256 checksum
        of the current document content.

    Returns:
        bool: True if the document hash is unchanged (needs skipping), False otherwise.
    """
    try:
        table = get_table()
        response = table.get_item(Key={"doc_id": doc_id})
        item = response.get("Item")
        if item and item.get("content_hash") == new_hash and item.get("status") == "COMPLETED":
            return True
    except Exception as e:
        print(f"Error checking document hash: {e}")
    return False


def check_document_hashes_batch(doc_hash_map: dict[str, str]) -> set[str]:
    """
    Scans DynamoDB once and returns a set of document IDs that are already completed
    and unchanged. Highly performant and simple.
    """
    try:
        table = get_table()
        # Scan only the key fields. 'status' is an AWS reserved keyword, so we alias it to #s
        response = table.scan(
            ProjectionExpression="doc_id, content_hash, #s",
            ExpressionAttributeNames={"#s": "status"},
        )
        items = response.get("Items", [])

        # Build in-memory set of completed/pending document IDs where hashes match
        return {item["doc_id"] for item in items if item.get("status") in ("COMPLETED", "PENDING") and item.get("content_hash") == doc_hash_map.get(item["doc_id"])}
    except Exception as e:
        print(f"Error scanning document hashes: {e}")
        return set()


def update_document_hash(doc_id: str, new_hash: str, status: str = "COMPLETED") -> None:
    """
    Updates or inserts the document sync status and hash in DynamoDB.

    Args:
        doc_id (str): The unique identifier of the document.
        new_hash (str): The computed checksum to record.
        status (str): Ingestion status ("PENDING" or "COMPLETED").
    """
    try:
        table = get_table()
        table.put_item(Item={"doc_id": doc_id, "content_hash": new_hash, "status": status})
    except Exception as e:
        print(f"Error updating document hash: {e}")


def delete_document_vectors(doc_id: str) -> None:
    """
    Deletes all existing points/vectors associated with the given doc_id from Qdrant.
    This prevents stale chunks from remaining in the index when content is updated.

    Args:
        doc_id (str): The unique identifier of the document.
    """
    client = get_qdrant_client()
    try:
        if client.collection_exists(settings.qdrant_collection):
            client.delete(
                collection_name=settings.qdrant_collection,
                points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
            )
    except Exception as e:
        print(f"Error deleting document vectors: {e}")


def save_chunks_to_qdrant(doc_id: str, doc_url: str, chunks: list[str], embeddings: list[list[float]]) -> None:
    """
    Upserts chunk texts, embeddings, and metadata payloads to the Qdrant index.
    Clears any existing vectors for the document first to prevent duplicates.

    Args:
        doc_id (str): The document ID.
        doc_url (str): The source URL.
        chunks (list[str]): The plain text segments.
        embeddings (list[list[float]]): Corresponding Bedrock embedding vectors.
    """
    # 1. Wipes out any old chunks first
    delete_document_vectors(doc_id)

    client = get_qdrant_client()

    # 2. Ensure collection is created
    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )

    # 3. Build upsert list
    points = []
    for i, (chunk, vector) in enumerate(zip(chunks, embeddings, strict=False)):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}_chunk_{i}"))
        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "doc_id": doc_id,
                    "doc_url": doc_url,
                    "text": chunk,
                    "chunk_index": i,
                },
            )
        )

    client.upsert(collection_name=settings.qdrant_collection, points=points)
