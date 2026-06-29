import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import boto3

from indexer.parser import download_raw_docs, parse_raw_docs
from indexer.storage import check_document_hashes_batch, get_table, update_document_hash
from rag_shared.config import get_shared_settings

# Initialize AWS clients
s3_client = boto3.client("s3")
settings = get_shared_settings()


def _upload_to_s3(bucket: str, key: str, content: str) -> None:
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
    )


def _upload_and_mark_pending(doc, doc_id: str, content_hash: str) -> None:
    """Worker function to process a single document."""
    hashed_filename = hashlib.md5(doc_id.encode("utf-8")).hexdigest()
    s3_key = f"raw/pages/{hashed_filename}.json"

    doc_payload = {
        "doc_id": doc_id,
        "doc_url": doc_id,
        "title": doc.metadata.get("title", ""),
        "hash": content_hash,
        "page_content": doc.page_content,
    }

    # Upload to S3
    _upload_to_s3(
        bucket=settings.s3_bucket,
        key=s3_key,
        content=json.dumps(doc_payload),
    )

    # Mark state as PENDING in DynamoDB
    update_document_hash(doc_id, content_hash, status="PENDING")


def _prune_deleted_documents(crawled_doc_ids: set[str]) -> int:
    """
    Finds documents in DynamoDB that no longer exist in the crawled set,
    and removes them from DynamoDB, S3, and Qdrant.
    """
    try:
        table = get_table()

        # 1. Scan DynamoDB for all existing doc_ids
        response = table.scan(ProjectionExpression="doc_id")
        db_items = response.get("Items", [])
        db_doc_ids = {item["doc_id"] for item in db_items}

        # 2. Identify orphaned documents (in DB but not in crawled set)
        orphaned_ids = db_doc_ids - crawled_doc_ids
        if not orphaned_ids:
            return 0

        print(f"Found {len(orphaned_ids)} orphaned documents to prune.")

        # 3. Import delete function
        from indexer.storage import delete_document_vectors

        pruned_count = 0
        for doc_id in orphaned_ids:
            try:
                # A. Delete vectors from Qdrant Cloud
                delete_document_vectors(doc_id)

                # B. Delete raw payload from S3
                hashed_filename = hashlib.md5(doc_id.encode("utf-8")).hexdigest()
                s3_key = f"raw/pages/{hashed_filename}.json"
                s3_client.delete_object(Bucket=settings.s3_bucket, Key=s3_key)

                # C. Delete tracking entry from DynamoDB
                table.delete_item(Key={"doc_id": doc_id})

                pruned_count += 1
                print(f"Pruned orphaned document: {doc_id}")
            except Exception as e:
                print(f"Failed to prune document {doc_id}: {e}")

        return pruned_count
    except Exception as e:
        print(f"Error during pruning execution: {e}")
        return 0


def run_crawler() -> int:
    """
    Downloads raw LLMs file, parses into pages, hashes each page,
    and concurrently uploads changed pages to S3 as serialized JSON.
    """
    raw_text = download_raw_docs()
    documents = parse_raw_docs(raw_text)

    # 1. Pre-calculate hashes for all crawled documents
    doc_hash_map = {}
    doc_by_id = {}
    for doc in documents:
        doc_id = doc.metadata["url"]
        content_hash = hashlib.md5(doc.page_content.encode("utf-8")).hexdigest()
        doc_hash_map[doc_id] = content_hash
        doc_by_id[doc_id] = doc

    # 2. Check hashes in DynamoDB using batch querying (100 at a time)
    unchanged_ids = check_document_hashes_batch(doc_hash_map)

    # 3. Filter documents that need uploading (new or changed)
    to_upload = []
    for doc_id, content_hash in doc_hash_map.items():
        if doc_id not in unchanged_ids:
            to_upload.append((doc_by_id[doc_id], doc_id, content_hash))

    # 4. Concurrently execute the uploads if changes are detected
    if to_upload:
        # Unpack list of tuples [(doc, id, hash)] -> three parallel tuples
        docs, doc_ids, content_hashes = zip(*to_upload, strict=True)

        with ThreadPoolExecutor(max_workers=20) as executor:
            # Force evaluation of map to propagate exceptions raised in threads
            list(executor.map(_upload_and_mark_pending, docs, doc_ids, content_hashes))

    # 5. Prune any orphaned documents
    pruned_count = _prune_deleted_documents(set(doc_hash_map.keys()))
    if pruned_count > 0:
        print(f"Pruning complete. Removed {pruned_count} orphaned documents.")

    return len(to_upload)
