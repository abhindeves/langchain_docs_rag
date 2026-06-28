import asyncio
import os
import uuid
from typing import Any

import boto3
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    Modifier,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from rag_shared.config import get_shared_settings
from rag_shared.embeddings import Embedder

# Initialize clients using shared settings config
settings = get_shared_settings()
dynamodb: Any = boto3.resource("dynamodb", region_name=settings.aws_region)
embedder = Embedder()

_sparse_model = None


def get_sparse_model():
    """Lazily loads and returns the FastEmbed BM25 sparse text embedder."""
    global _sparse_model
    if _sparse_model is None:
        # Set cache path to /tmp/fastembed for write permissions in Lambda environment
        os.environ["FASTEMBED_CACHE_PATH"] = "/tmp/fastembed"
        from fastembed import SparseTextEmbedding

        _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    return _sparse_model


TABLE_NAME = "DocumentSyncStatus"


def get_qdrant_client() -> QdrantClient:
    """
    Initializes and returns a Qdrant client connection.
    """
    if not settings.qdrant_host:
        raise ValueError("Qdrant host URL is not configured.")
    return QdrantClient(
        url=settings.qdrant_host,
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


async def save_chunks_to_qdrant(doc_id: str, doc_url: str, chunks: list[str]) -> None:
    """
    Upserts chunk texts, embeddings, and metadata payloads to the Qdrant index.
    Clears any existing vectors for the document first to prevent duplicates.

    Args:
        doc_id (str): The document ID.
        doc_url (str): The source URL.
        chunks (list[str]): The plain text segments.
    """
    if not chunks:
        return

    # 1. Wipes out any old chunks first
    delete_document_vectors(doc_id)

    client = get_qdrant_client()

    # 2. Ensure collection is created with hybrid vector support (dense + sparse)
    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config={"dense_vector": VectorParams(size=1024, distance=Distance.COSINE)},
            sparse_vectors_config={"bm25_sparse_vector": SparseVectorParams(modifier=Modifier.IDF)},
        )

    # 3. Ensure payload index exists for filtering/deleting documents by doc_id
    try:
        from qdrant_client.models import PayloadSchemaType

        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="doc_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception as e:
        print(f"Payload index creation check warning: {e}")

    # 3. Generate dense embeddings asynchronously in parallel
    embeddings = await embedder.embed_documents(chunks)

    # 4. Generate sparse embeddings using FastEmbed (bm25) in a thread pool
    sparse_model = get_sparse_model()
    sparse_embeddings = await asyncio.to_thread(lambda sm=sparse_model, bc=chunks: list(sm.embed(bc)))

    # 5. Prepare Points
    points = []
    for i, (chunk, dense_vector, sparse_vector) in enumerate(zip(chunks, embeddings, sparse_embeddings, strict=True)):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}_chunk_{i}"))
        points.append(
            PointStruct(
                id=point_id,
                vector={
                    "dense_vector": dense_vector,
                    "bm25_sparse_vector": SparseVector(
                        indices=sparse_vector.indices.tolist(),
                        values=sparse_vector.values.tolist(),
                    ),
                },
                payload={
                    "doc_id": doc_id,
                    "doc_url": doc_url,
                    "text": chunk,
                    "chunk_index": i,
                },
            )
        )

    # 6. Upsert to Qdrant
    client.upsert(collection_name=settings.qdrant_collection, points=points)
