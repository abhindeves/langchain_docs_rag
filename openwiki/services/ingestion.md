---
type: Service Documentation
title: Ingestion Service
description: Documentation for the event-driven serverless ingestion pipeline that crawls, processes, and embeds documents.
tags: [ingestion, lambda, sqs, s3, bedrock, qdrant]
---

# Ingestion Service

The Ingestion Service is responsible for crawling documentation sources, processing the content, and preparing it for retrieval. It's an event-driven, serverless pipeline designed for scalability and efficiency.

## Ingestion Pipeline

The ingestion process is divided into several stages, orchestrated by AWS Lambda and SQS.

1.  **Dispatch:** The `master_crawl_handler` Lambda function is triggered by a scheduled EventBridge event. It identifies the target URLs to be crawled and sends a message for each URL to the `rag-crawler-queue` SQS queue.
    *   **Source:** [`services/indexer-service/src/indexer/lambda_handler.py`](../../services/indexer-service/src/indexer/lambda_handler.py)

2.  **Crawl & Deduplicate:** The `manifest_crawl_handler` Lambda function is triggered by messages in the SQS queue. This function is responsible for:
    *   Downloading the raw content from the target URL.
    *   Performing deduplication using an S3 manifest file. This avoids costly database lookups by tracking content hashes in a file in S3.
    *   Uploading new or modified content to an S3 bucket.
    *   Updating the document's status to `PENDING` in a DynamoDB table.
    *   **Source:** [`services/indexer-service/src/indexer/manifest_crawler.py`](../../services/indexer-service/src/indexer/manifest_crawler.py)

3.  **Chunking and Embedding:** An S3 trigger invokes a worker Lambda when new raw content is uploaded. This worker, `s3_event_handler`, performs the following:
    *   Downloads the raw document from S3.
    *   Checks if the document's hash has changed to prevent re-processing.
    *   Splits the document into smaller chunks using custom text splitters.
    *   Generates embeddings for each chunk using Amazon Bedrock.
    *   Saves the chunks and their embeddings to the Qdrant vector database.
    *   Updates the document's status to `COMPLETED` in DynamoDB.
    *   **Source:** [`services/indexer-service/src/indexer/lambda_handler.py`](../../services/indexer-service/src/indexer/lambda_handler.py)

## Core Components

*   **`lambda_handler.py`:** Contains the main AWS Lambda handlers for the different stages of the ingestion pipeline.
*   **`manifest_crawler.py`:** Implements the logic for crawling sources and performing deduplication using S3 manifests.
*   **`chunker.py`:** Contains the logic for splitting documents into smaller chunks.
*   **`custom_splitters.py`:** Provides custom, lightweight implementations of text splitters, optimized for the Lambda environment.
*   **`parser.py`:** Handles downloading and parsing of raw document content.
*   **`storage.py`:** Manages interactions with Qdrant and DynamoDB for storing embeddings and tracking document status.

## Key Optimizations

As detailed in [ADR 0002](../../docs/adr/0002-decouple-ingestion-dependencies.md), the ingestion service has been heavily optimized by:
*   Removing heavy dependencies like LangChain and FastEmbed.
*   Implementing custom, lightweight text splitters.
*   Offloading sparse vector generation to Qdrant's server-side inference.
*   Using a minimal, direct REST client for Qdrant.

These optimizations have resulted in significant reductions in Lambda package size, memory usage, and cold start times.
