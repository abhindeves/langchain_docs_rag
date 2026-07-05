import json
import logging
import uuid
from typing import Any

import boto3
import urllib3

from rag_shared.config import get_shared_settings
from rag_shared.embeddings import Embedder

# Initialize clients using shared settings config
settings = get_shared_settings()
dynamodb: Any = boto3.resource("dynamodb", region_name=settings.aws_region)
logger = logging.getLogger(__name__)

embedder = Embedder()


TABLE_NAME = "DocumentSyncStatus"


class MiniQdrantClient:
    def __init__(self, url: str, api_key: str | None = None):
        self.url = url.rstrip("/")
        # Initialize PoolManager for Keep-Alive connection pooling
        self.http = urllib3.PoolManager(maxsize=3)
        self.headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            self.headers["api-key"] = api_key

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        url = f"{self.url}{path}"
        data = json.dumps(body) if body is not None else None

        try:
            resp = self.http.request(method, url, body=data, headers=self.headers, timeout=10.0)

            # 404 on GET means the collection/object does not exist
            if method == "GET" and resp.status == 404:
                return None

            if resp.status not in (200, 201):
                err_text = resp.data.decode("utf-8") if resp.data else ""
                raise RuntimeError(f"Qdrant REST error {resp.status}: {err_text}")

            return json.loads(resp.data.decode("utf-8"))
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise e
            raise RuntimeError(f"Network error connecting to Qdrant REST: {e}") from e

    def collection_exists(self, collection_name: str) -> bool:
        res = self._request("GET", f"/collections/{collection_name}")
        return res is not None

    def create_collection(self, collection_name: str, vectors_config: dict, sparse_vectors_config: dict | None = None) -> None:
        payload = {"vectors": vectors_config}
        if sparse_vectors_config:
            payload["sparse_vectors"] = sparse_vectors_config
        self._request("PUT", f"/collections/{collection_name}", payload)

    def create_payload_index(self, collection_name: str, field_name: str, field_schema: str) -> None:
        payload = {"field_name": field_name, "field_schema": field_schema}
        self._request("PUT", f"/collections/{collection_name}/index", payload)

    def upsert(self, collection_name: str, points: list[dict]) -> None:
        self._request("PUT", f"/collections/{collection_name}/points", {"points": points})

    def delete(self, collection_name: str, points_selector: dict) -> None:
        self._request("POST", f"/collections/{collection_name}/points/delete", points_selector)


def get_qdrant_client() -> MiniQdrantClient:
    """
    Initializes and returns a MiniQdrantClient REST connection.
    """
    if not settings.qdrant_host:
        raise ValueError("Qdrant host URL is not configured.")
    return MiniQdrantClient(
        url=settings.qdrant_host,
        api_key=settings.qdrant_api_key,
    )


def get_table():
    """
    Retrieves the DynamoDB table instance.
    """
    table = dynamodb.Table(TABLE_NAME)
    table.load()  # Will trigger exception if table does not exist
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
        logger.error(f"Error checking document hash for {doc_id}: {e}", exc_info=True)
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
        logger.error(f"Error scanning document hashes in DynamoDB: {e}", exc_info=True)
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
        logger.error(f"Error updating document hash for {doc_id} to status {status}: {e}", exc_info=True)


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
                points_selector={"filter": {"must": [{"key": "doc_id", "match": {"value": doc_id}}]}},
            )
    except Exception as e:
        logger.error(f"Error deleting document vectors for {doc_id}: {e}", exc_info=True)


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
            vectors_config={"dense_vector": {"size": 1024, "distance": "Cosine"}},
            sparse_vectors_config={"bm25_sparse_vector": {"modifier": "idf"}},
        )

    # 3. Ensure payload index exists for filtering/deleting documents by doc_id
    try:
        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="doc_id",
            field_schema="keyword",
        )
    except Exception as e:
        logger.warning(f"Payload index creation check warning: {e}")

    # 3. Generate dense embeddings asynchronously in parallel
    logger.info(f"Generating dense embeddings using model '{settings.embedding_model}'...")
    embeddings = await embedder.embed_documents(chunks)

    # 4. Prepare Points with server-side BM25 sparse vector generation
    points = []
    for i, (chunk, dense_vector) in enumerate(zip(chunks, embeddings, strict=True)):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}_chunk_{i}"))
        points.append(
            {
                "id": point_id,
                "vector": {
                    "dense_vector": dense_vector,
                    "bm25_sparse_vector": {
                        "text": chunk,
                        "model": "Qdrant/bm25",
                    },
                },
                "payload": {
                    "doc_id": doc_id,
                    "doc_url": doc_url,
                    "text": chunk,
                    "chunk_index": i,
                },
            }
        )

    # 6. Upsert to Qdrant
    logger.info(f"Upserting {len(points)} points to Qdrant collection '{settings.qdrant_collection}'...")
    client.upsert(collection_name=settings.qdrant_collection, points=points)
    logger.info(f"Successfully saved {len(chunks)} chunks to Qdrant for document '{doc_id}'.")
