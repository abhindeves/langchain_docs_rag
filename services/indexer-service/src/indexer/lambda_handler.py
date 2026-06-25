"""
AWS Lambda event handlers for crawling/dispatching and worker queue processing.
"""

import asyncio
import hashlib
import json
import logging

from indexer.chunker import chunk_markdown_docs
from indexer.crawler import run_crawler
from indexer.parser import download_from_s3, parse_raw_docs
from indexer.storage import (
    check_document_hash,
    save_chunks_to_qdrant,
    update_document_hash,
)
from rag_shared.embeddings import Embedder

# Configure Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global Embedder client (singleton reuse)
embedder = Embedder()


def crawl_handler(event, context) -> dict:
    """
    Crawler handler triggered by EventBridge cron schedule or manual invocation.
    Downloads raw document, saves to S3, and dispatches a notification job to SQS.
    """
    logger.info("Executing crawler/dispatcher lambda handler...")
    result = run_crawler()
    return {
        "statusCode": 200,
        "body": json.dumps(
            {"message": "Crawl executed successfully", "jobs_dispatched": result}
        ),
    }


async def _process_record_async(record: dict) -> None:
    """
    Processes the raw file key from SQS:
    1. Downloads latest raw content from S3.
    2. Parses content into individual Documents.
    3. For each Document:
       - Computes a content hash.
       - Compares against DynamoDB status (skips if matches).
       - If changed, chunks the markdown, embeds it, and writes to Qdrant.
       - Updates DynamoDB sync state to the new hash.
    """
    body = json.loads(record["body"])
    s3_bucket = body.get("s3_bucket")
    s3_key = body.get("s3_key")
    raw_text = download_from_s3(s3_bucket, s3_key)
    docs = parse_raw_docs(raw_text)
    for doc in docs:
        doc_id = doc.metadata["url"]
        content_hash = hashlib.md5(doc.page_content.encode("utf-8")).hexdigest()
        if check_document_hash(doc_id, content_hash):
            continue

        chunks = chunk_markdown_docs([doc])
        chunk_texts = [c.page_content for c in chunks]
        embeddings = await embedder.embed_documents(chunk_texts)
        save_chunks_to_qdrant(doc_id, doc.metadata["url"], chunk_texts, embeddings)
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
            logger.error(
                f"Error processing SQS record {record.get('messageId')}: {str(e)}"
            )
            # Re-raise the exception so SQS retries the message or puts it in the DLQ
            raise e

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Batch processed successfully"}),
    }
