"""
S3 Manifest-based Crawler module for downloading, deduplicating,
uploading, and pruning raw documents.
"""

import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

from indexer.parser import download_raw_docs, parse_raw_docs
from indexer.storage import delete_document_vectors, get_table, update_document_hash
from rag_shared.config import get_shared_settings

logger = logging.getLogger(__name__)
s3_client = boto3.client("s3")
settings = get_shared_settings()


def _get_manifest(bucket: str, key: str) -> dict:
    """
    Downloads the manifest file from S3. Returns an empty dict if it does not exist.
    """
    try:
        logger.info(f"Downloading manifest from s3://{bucket}/{key}")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "NoSuchKey":
            logger.info("No manifest file found. Initializing new manifest.")
            return {}
        logger.error(f"Error fetching manifest from S3: {e}", exc_info=True)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error loading manifest: {e}", exc_info=True)
        raise e


def _save_manifest(bucket: str, key: str, manifest: dict) -> None:
    """
    Uploads the updated manifest file to S3.
    """
    try:
        logger.info(f"Saving manifest back to s3://{bucket}/{key}")
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(manifest, indent=2),
            ContentType="application/json",
        )
    except Exception as e:
        logger.error(f"Failed to save manifest to S3: {e}", exc_info=True)
        raise e


def _upload_to_s3(bucket: str, key: str, content: str) -> None:
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
    )


def get_sanitized_name(url: str) -> str:
    """
    Converts a URL to a safe, human-readable S3 directory / filename prefix.
    Replaces non-alphanumeric characters (like slashes, colons, dots) with underscores.
    """
    parsed = urlparse(url)
    combined = f"{parsed.netloc}{parsed.path}"
    # Replace anything that isn't a letter, number, hyphen, or underscore with a single underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", combined)
    # Remove duplicate underscores and strip trailing/leading ones
    return re.sub(r"_+", "_", sanitized).strip("_")


def _upload_and_mark_pending(doc, doc_id: str, content_hash: str, target_url_name: str) -> str:
    """
    Uploads the document to S3 and updates its sync status to PENDING in DynamoDB.
    Returns the s3_key where the document was stored.
    """
    hashed_filename = hashlib.md5(doc_id.encode("utf-8")).hexdigest()
    s3_key = f"raw/pages/{target_url_name}/{hashed_filename}.json"

    doc_payload = {
        "doc_id": doc_id,
        "doc_url": doc_id,
        "title": doc.metadata.get("title", ""),
        "hash": content_hash,
        "page_content": doc.page_content,
    }

    logger.info(f"Uploading raw page payload to S3 (key: {s3_key}) and marking status as PENDING in DynamoDB for document: {doc_id}")
    _upload_to_s3(
        bucket=settings.s3_bucket,
        key=s3_key,
        content=json.dumps(doc_payload),
    )

    # Update DynamoDB sync status to PENDING
    update_document_hash(doc_id, content_hash, status="PENDING")
    return s3_key


def run_manifest_crawler(target_url: str) -> int:
    """
    Downloads raw documentation, parses pages, hashes content,
    and deduplicates using an S3 manifest file (manifests/{target_url_name}.json).
    Prunes stale pages using the manifest and saves the updated manifest back to S3.
    """
    logger.info(f"Starting manifest crawler for URL: {target_url}")

    # 1. Determine the manifest key in S3 based on the sanitized target_url name
    target_url_name = get_sanitized_name(target_url)
    manifest_key = f"manifests/{target_url_name}.json"

    # 2. Fetch the current manifest state from S3
    manifest = _get_manifest(settings.s3_bucket, manifest_key)

    # 3. Download and parse raw documents
    raw_text = download_raw_docs(target_url)
    documents = parse_raw_docs(raw_text)

    # 4. Map crawled documents and calculate their content hashes
    crawled_docs_map = {doc.metadata["url"]: doc for doc in documents}
    crawled_hashes = {doc_id: hashlib.md5(doc.page_content.encode("utf-8")).hexdigest() for doc_id, doc in crawled_docs_map.items()}

    # 5. Deduplicate: Find which documents are new or have changed content
    to_upload = [(crawled_docs_map[doc_id], doc_id, current_hash) for doc_id, current_hash in crawled_hashes.items() if doc_id not in manifest or manifest[doc_id].get("hash") != current_hash]

    # 6. Concurrently upload changed documents
    if to_upload:
        # Define a task for executor
        def process_upload(task):
            doc_obj, d_id, c_hash = task
            s3_k = _upload_and_mark_pending(doc_obj, d_id, c_hash, target_url_name)
            return d_id, {"hash": c_hash, "s3_key": s3_k}

        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(process_upload, to_upload))

        # Update the manifest dictionary with the new entries
        for doc_id, entry in results:
            manifest[doc_id] = entry

    # 7. Prune deleted documents (orphaned documents in the manifest but not in the currently crawled set)
    orphaned_ids = set(manifest.keys()) - set(crawled_hashes.keys())
    if orphaned_ids:
        logger.info(f"Found {len(orphaned_ids)} orphaned documents to prune based on S3 manifest.")
        table = get_table()

        for doc_id in orphaned_ids:
            try:
                entry = manifest[doc_id]
                s3_key_to_delete = entry.get("s3_key")

                # A. Delete vectors from Qdrant Cloud
                logger.info(f"Pruning: Deleting Qdrant vectors for orphaned document {doc_id}...")
                delete_document_vectors(doc_id)

                # B. Delete raw payload from S3
                if s3_key_to_delete:
                    logger.info(f"Pruning: Deleting S3 raw file {s3_key_to_delete}...")
                    try:
                        s3_client.delete_object(Bucket=settings.s3_bucket, Key=s3_key_to_delete)
                    except ClientError as s3_err:
                        logger.warning(f"S3 deletion failed for key {s3_key_to_delete}: {s3_err}")

                # C. Delete tracking entry from DynamoDB
                logger.info(f"Pruning: Deleting DynamoDB status record for {doc_id}...")
                try:
                    table.delete_item(Key={"doc_id": doc_id})
                except Exception as ddb_err:
                    logger.warning(f"DynamoDB deletion failed for {doc_id}: {ddb_err}")

                # D. Remove from manifest dict
                manifest.pop(doc_id, None)
                logger.info(f"Successfully pruned orphaned document from manifest: {doc_id}")

            except Exception as prune_err:
                logger.error(f"Failed to prune document {doc_id}: {prune_err}", exc_info=True)

    # 8. Upload the updated manifest back to S3
    _save_manifest(settings.s3_bucket, manifest_key, manifest)

    logger.info(f"Manifest crawler run finished. Uploaded and queued {len(to_upload)} new/changed files.")
    return len(to_upload)
