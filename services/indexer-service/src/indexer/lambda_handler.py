"""
AWS Lambda event handlers for crawling/dispatching and worker queue processing.
"""

import asyncio
import json
import logging

from langchain_core.documents import Document

from indexer.chunker import chunk_markdown_docs
from indexer.crawler import run_crawler
from indexer.parser import download_from_s3
from indexer.storage import (
    check_document_hash,
    save_chunks_to_qdrant,
    update_document_hash,
)

# Configure Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def crawl_handler(event, context) -> dict:
    """
    Crawler handler triggered by EventBridge cron schedule or manual invocation.
    Downloads raw document, saves to S3, and dispatches a notification job to SQS.
    """
    logger.info("Executing crawler/dispatcher lambda handler...")
    result = run_crawler()
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Crawl executed successfully", "jobs_dispatched": result}),
    }


async def _process_record_async(record: dict) -> None:
    """
    Processes the raw file key from SQS:
    1. Parses S3 bucket/key from SQS body (handles native S3 Events and custom payloads).
    2. Downloads document JSON from S3.
    3. Reconstructs Document object directly.
    4. Computes content hash and checks DynamoDB status.
    5. If changed/new, chunks, embeds, writes to Qdrant, and updates DynamoDB.
    """
    body = json.loads(record["body"])

    # Check if this is a native S3 Event Notification or mock local notification
    if "Records" in body and len(body["Records"]) > 0 and "s3" in body["Records"][0]:
        s3_info = body["Records"][0]["s3"]
        s3_bucket = s3_info["bucket"]["name"]
        s3_key = s3_info["object"]["key"]
    else:
        # Fallback for manual/legacy payloads
        s3_bucket = body.get("s3_bucket")
        s3_key = body.get("s3_key")

    if not s3_bucket or not s3_key:
        raise ValueError(f"S3 coordinates missing in record body: {body}")

    raw_text = download_from_s3(s3_bucket, s3_key)

    # The downloaded file is serialized JSON containing page content and metadata
    data = json.loads(raw_text)

    doc_id = data["doc_id"]
    doc_url = data["doc_url"]
    title = data["title"]
    content_hash = data["hash"]
    page_content = data["page_content"]

    # Deduplication check
    if check_document_hash(doc_id, content_hash):
        logger.info(f"Document {doc_id} has not changed. Skipping ingestion.")
        return

    doc = Document(
        page_content=page_content,
        metadata={
            "title": title,
            "url": doc_url,
            "source": doc_url,
        },
    )

    chunks = chunk_markdown_docs([doc])
    chunk_texts = [c.page_content for c in chunks]
    await save_chunks_to_qdrant(doc_id, doc_url, chunk_texts)
    update_document_hash(doc_id, content_hash)


def worker_handler(event, context) -> dict:
    """
    Worker handler triggered by Amazon SQS Queue messages.
    Processes S3 raw documents, parsing and indexing only modified pages.
    """
    logger.info("Executing worker queue lambda handler...")

    for record in event.get("Records", []):
        try:
            # Runs the async pipeline for this specific record
            asyncio.run(_process_record_async(record))
        except Exception as e:
            logger.error(f"Error processing SQS record {record.get('messageId')}: {str(e)}")

            # Check SQS receive count to decide if we mark DynamoDB as FAILED
            try:
                receive_count = int(record.get("attributes", {}).get("ApproximateReceiveCount", 1))
                if receive_count >= 3:
                    body = json.loads(record["body"])
                    s3_info = body["Records"][0]["s3"]
                    s3_bucket = s3_info["bucket"]["name"]
                    s3_key = s3_info["object"]["key"]
                    try:
                        # Try to download and parse the JSON file to get doc_id and hash
                        raw_text = download_from_s3(s3_bucket, s3_key)
                        data = json.loads(raw_text)
                        doc_id = data.get("doc_id")
                        content_hash = data.get("hash")
                        if doc_id and content_hash:
                            logger.warning(f"Marking document {doc_id} as FAILED in DynamoDB (attempts: {receive_count})")
                            update_document_hash(doc_id, content_hash, status="FAILED")
                    except Exception:
                        pass
            except Exception as ddb_err:
                logger.error(f"Failed to update document status to FAILED in DynamoDB: {str(ddb_err)}")

            # Re-raise the exception so SQS retries the message or puts it in the DLQ
            raise e

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Batch processed successfully"}),
    }
