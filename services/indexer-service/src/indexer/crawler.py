"""
Crawler module to download llms-full.txt, parse into individual pages,
upload changed docs to S3, and trigger processing jobs.
"""

import hashlib
import json

import boto3

from indexer.parser import download_raw_docs, parse_raw_docs
from indexer.storage import check_document_hash, update_document_hash
from shared.config import get_shared_settings

# Initialize AWS clients
s3_client = boto3.client("s3")
sqs_client = boto3.client("sqs")
settings = get_shared_settings()


def _upload_to_s3(bucket: str, key: str, content: str) -> None:
    """
    Uploads raw text content to the S3 staging bucket.

    Args:
        bucket (str): S3 bucket name.
        key (str): S3 object key path.
        content (str): Raw document content string.
    """
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
    )


def _push_to_sqs(queue_url: str, payload: dict) -> None:
    """
    Sends a single document ingestion job to the SQS queue.

    Args:
        queue_url (str): The Amazon SQS Queue URL.
        payload (dict): The message dictionary containing S3 details.
    """
    sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(payload),
    )


def run_crawler() -> int:
    """
    Downloads raw LLMs file, parses into pages, hashes each page,
    uploads changed pages to S3, and dispatches them to SQS.

    Returns:
        int: Number of update jobs pushed to SQS.
    """
    raw_text = download_raw_docs()
    documents = parse_raw_docs(raw_text)

    dispatched_count = 0
    for doc in documents:
        doc_id = doc.metadata["url"]
        content_hash = hashlib.md5(doc.page_content.encode("utf-8")).hexdigest()

        # Check if the page is already indexed and unchanged in DynamoDB
        if check_document_hash(doc_id, content_hash):
            continue

        # Deterministic flat filename for the S3 object key
        hashed_filename = hashlib.md5(doc_id.encode("utf-8")).hexdigest()
        s3_key = f"raw/pages/{hashed_filename}.txt"

        # 1. Upload just this single page's text to S3
        _upload_to_s3(
            bucket=settings.s3_bucket,
            key=s3_key,
            content=doc.page_content,
        )

        # 2. Push metadata payload to SQS for this page
        _push_to_sqs(
            queue_url=settings.sqs_queue_url,
            payload={
                "s3_bucket": settings.s3_bucket,
                "s3_key": s3_key,
                "doc_id": doc_id,
                "doc_url": doc_id,
                "title": doc.metadata.get("title", ""),
                "hash": content_hash,
            },
        )

        # 3. Mark the document state as PENDING in DynamoDB
        update_document_hash(doc_id, content_hash, status="PENDING")
        dispatched_count += 1

    return dispatched_count
