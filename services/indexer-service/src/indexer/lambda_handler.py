"""
AWS Lambda event handlers for crawling/dispatching and worker queue processing.
"""

import asyncio
import json
import logging

from langchain_core.documents import Document

from indexer.chunker import chunk_markdown_docs
from indexer.crawler import run_crawler
from indexer.manifest_crawler import run_manifest_crawler
from indexer.parser import download_from_s3
from indexer.storage import (
    check_document_hash,
    save_chunks_to_qdrant,
    update_document_hash,
)

# Configure Logging
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)


def crawl_handler(event, context) -> dict:
    """
    Crawler handler triggered by EventBridge cron schedule or manual invocation.
    Downloads raw document, saves to S3, and dispatches a notification job to SQS.
    """
    logger.info("Executing crawler/dispatcher lambda handler...")
    result = run_crawler()
    logger.info(f"Crawler/Dispatcher execution complete. Dispatched {result} raw documents to S3.")
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Crawl executed successfully", "jobs_dispatched": result}),
    }


def manifest_crawl_handler(event, context) -> dict:
    """
    Manifest-based Crawler handler triggered manually or via SQS.
    Deduplicates using an S3 manifest file and updates status to PENDING in DynamoDB.
    """
    logger.info("Executing manifest-based crawler lambda handler...")

    target_url = "https://docs.langchain.com/llms-full.txt"
    if isinstance(event, dict):
        if "target_url" in event:
            target_url = event["target_url"]
        elif "Records" in event and len(event["Records"]) > 0:
            # Check for SQS payload
            try:
                body = json.loads(event["Records"][0]["body"])
                if isinstance(body, dict) and "target_url" in body:
                    target_url = body["target_url"]
                elif isinstance(body, str):
                    target_url = body
            except Exception as parse_err:
                logger.warning(f"Failed to parse SQS body as JSON, using raw body: {parse_err}")
                target_url = event["Records"][0]["body"]

    result = run_manifest_crawler(target_url)
    logger.info(f"Manifest Crawler execution complete. Dispatched {result} raw documents.")
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Manifest crawl executed successfully", "jobs_dispatched": result}),
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

    logger.info(f"SQS record message {record.get('messageId')} coordinates parsed successfully: s3://{s3_bucket}/{s3_key}")
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

    logger.info(f"Reconstructing document: {doc_id} (title: '{title}'). Initiating chunking...")
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
    logger.info(f"Successfully processed and indexed document: {doc_id}. Synced status to COMPLETED.")


def worker_handler(event, context) -> dict:
    """
    Worker handler triggered by Amazon SQS Queue messages.
    Processes S3 raw documents, parsing and indexing only modified pages.
    """
    records = event.get("Records", [])
    logger.info(f"Executing worker queue lambda handler. Received SQS batch containing {len(records)} records.")

    for record in records:
        try:
            logger.info(f"Starting async processing for SQS record ID: {record.get('messageId')}")
            # Runs the async pipeline for this specific record
            asyncio.run(_process_record_async(record))
            logger.info(f"Finished processing SQS record ID: {record.get('messageId')} successfully.")
        except Exception as e:
            logger.error(f"Error processing SQS record {record.get('messageId')}: {str(e)}", exc_info=True)

            # Check SQS receive count to decide if we mark DynamoDB as FAILED
            try:
                receive_count = int(record.get("attributes", {}).get("ApproximateReceiveCount", 1))
                logger.warning(f"SQS record ID {record.get('messageId')} failed attempt {receive_count}/3.")
                if receive_count >= 3:
                    body = json.loads(record["body"])
                    s3_info = body["Records"][0]["s3"]
                    s3_bucket = s3_info["bucket"]["name"]
                    s3_key = s3_info["object"]["key"]
                    try:
                        # Try to download and parse the JSON file to get doc_id and hash
                        logger.warning(f"SQS attempts exceeded threshold. Marking document status as FAILED for source coordinates: s3://{s3_bucket}/{s3_key}")
                        raw_text = download_from_s3(s3_bucket, s3_key)
                        data = json.loads(raw_text)
                        doc_id = data.get("doc_id")
                        content_hash = data.get("hash")
                        if doc_id and content_hash:
                            logger.error(f"Marking document {doc_id} as FAILED in DynamoDB (attempts: {receive_count})")
                            update_document_hash(doc_id, content_hash, status="FAILED")
                    except Exception as parse_err:
                        logger.error(f"Failed to extract document identifiers from raw S3 coordinates to mark FAILED state: {str(parse_err)}")
            except Exception as ddb_err:
                logger.error(f"Failed to update document status to FAILED in DynamoDB: {str(ddb_err)}")

            # Re-raise the exception so SQS retries the message or puts it in the DLQ
            raise e

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Batch processed successfully"}),
    }
