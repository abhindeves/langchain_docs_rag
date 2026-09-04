---
type: Service Documentation
title: Ingestion Service
description: Documentation for the event-driven serverless ingestion pipeline that crawls, processes, and embeds documents.
tags: [ingestion, lambda, sqs, s3, bedrock, qdrant]
verified:
  - by: openwiki/0.5.0
    at: 2026-09-04T12:25:44.572Z
sources:
  - id: openwiki-source-af70149a354536b126186304
    resource: repo://docs/adr/0002-decouple-ingestion-dependencies.md
  - id: openwiki-source-0d7d57bc9732734adbf29b14
    resource: repo://services/indexer-service/src/indexer/lambda_handler.py
  - id: openwiki-source-53309d3d93deed43bfcac7af
    resource: repo://services/indexer-service/src/indexer/manifest_crawler.py
  - id: openwiki-source-495f1336040c4ee315812c25
    resource: repo://services/indexer-service/src/indexer/storage.py
generated: { by: "openwiki/0.5.0", at: "2026-09-04T12:25:44.572Z" }
---

# Ingestion Service

The Ingestion Service is responsible for crawling documentation sources, processing content, and preparing it for retrieval in the RAG platform. It is a highly optimized, event-driven, serverless pipeline designed for scalability, low-latency, and minimal operating costs.

## Architecture and Control Flow

The ingestion workflow relies on asynchronous message passing and event triggers to decouple ingestion stages, allowing for massive parallelization.

```mermaid
graph LR
    EB[EventBridge] --> MC[Master Crawler]
    MC --> Q[SQS Queue]
    Q --> ManC[Manifest Crawler]
    ManC --> S3Raw[(S3 Raw)]
    S3Raw --> Trig[S3 Event Trigger]
    Trig --> Worker[Worker Lambda]
    Worker --> Bedrock[Amazon Bedrock]
    Worker --> Qdrant[(Qdrant DB)]
    Worker --> DDB[(DynamoDB)]
```

### Ingestion Stages

1.  **Dispatch:** Triggered by EventBridge, `master_crawl_handler` calculates crawl targets and distributes them as messages to the `rag-crawler-queue` (SQS).
2.  **Crawl & Deduplicate:** `manifest_crawl_handler` consumes SQS messages. It performs deduplication using a manifest file in S3 to avoid unnecessary database lookups, then uploads raw content to S3.
3.  **Chunking & Embedding:** An S3 trigger invokes the `s3_event_handler`. This worker parses content, applies lightweight text splitting, generates embeddings via Amazon Bedrock, and persists data into the Qdrant vector database, updating the document lifecycle state in DynamoDB.

## Core Modules

| Module | Responsibility |
| :--- | :--- |
| `lambda_handler.py` | Orchestrates the primary Lambda entrypoints. |
| `manifest_crawler.py` | Implements URL crawling and S3-based deduplication logic. |
| `chunker.py` | Orchestrates the document-to-chunk transformation. |
| `custom_splitters.py` | Lightweight text-splitting algorithms optimized for Lambda. |
| `parser.py` | Standardizes raw document parsing and content extraction. |
| `storage.py` | Manages stateful I/O with DynamoDB and vector indexing with Qdrant. |

## Operational Principles

### Optimization and Dependencies
As specified in [ADR 0002](repo://docs/adr/0002-decouple-ingestion-dependencies.md), the service minimizes cold start times and packaging overhead by:
*   Excluding heavy external frameworks like LangChain.
*   Replacing bloated embedding libraries with direct Bedrock API calls.
*   Utilizing custom, dependency-free text splitters in `custom_splitters.py`.

### Failure Semantics
The pipeline utilizes SQS with Dead-Letter Queues (DLQ) to isolate failing ingestion tasks. State tracking in DynamoDB (`PENDING`/`COMPLETED`) allows for idempotent retry logic, ensuring documents are not double-processed or left in an inconsistent state during partial failures.
