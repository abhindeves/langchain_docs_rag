---
type: Architecture Overview
title: System Architecture Overview
description: High-level architectural model of the RAG platform, focusing on the event-driven ingestion pipeline and data lifecycle from raw source to vector store.
tags: [architecture, aws, serverless, rag]
verified:
  - by: openwiki/0.5.0
    at: 2026-09-08T12:30:29.951Z
sources:
  - id: openwiki-source-b79fbbd921df689b4bbdc82f
    resource: repo://docker-compose.yml
  - id: openwiki-source-38f037d212ee358478211ba3
    resource: repo://docs/adr/0001-manifest-crawler-sqs-fanout.md
  - id: openwiki-source-af70149a354536b126186304
    resource: repo://docs/adr/0002-decouple-ingestion-dependencies.md
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "openwiki/0.5.0", at: "2026-09-08T12:30:29.951Z" }
---

# System Architecture Overview

This document provides a high-level model of the Serverless RAG Platform's architecture. The platform is designed as a production-grade, event-driven system leveraging AWS serverless services to manage data ingestion, semantic search, and quality evaluation.

## High-Level Communication Flow

The following diagram illustrates the interaction between the system's core components.

```mermaid
flowchart TB
    User((User)) --> API[API Service]
    API --> Ingestion[Ingestion Pipeline]
    API --> Eval[Evaluation Service]
    Ingestion --> Qdrant[(Qdrant Vector DB)]
    Eval --> Qdrant
    Eval --> Bedrock[Amazon Bedrock]
```
*System component interaction diagram.*

## Component Responsibilities

*   **API Service:** Acts as the primary interface for users, providing RESTful endpoints for hybrid semantic search.
*   **Ingestion Pipeline:** Automates the end-to-end transformation of raw data into searchable vector embeddings using Amazon SQS for asynchronous, scalable processing.
*   **Evaluation Service:** Assesses retrieval and generation quality against benchmarks to ensure consistent RAG performance.

## Data Lifecycle and Control Flow

The ingestion pipeline automates the transformation of external content into searchable vector embeddings.

```mermaid
flowchart LR
    EB[EventBridge] --> MC[Master Crawler]
    MC --> Q[SQS Queue]
    Q --> ManC[Manifest Crawler]
    ManC --> S3Raw[(S3 Raw Storage)]
    S3Raw --> S3Trigger[S3 Event Trigger]
    S3Trigger --> Worker[Worker Lambda]
    Worker --> Bedrock[Amazon Bedrock]
    Worker --> Qdrant[(Qdrant Vector DB)]
    Worker --> DDB[(DynamoDB Status)]
```
*Ingestion pipeline flow diagram.*

### Ingestion Pipeline Details

*   **Dispatch (EventBridge & Master Crawler):** An EventBridge Scheduler initiates a scheduled crawl. The Master Crawler Lambda identifies source URLs and dispatches them to an SQS queue.
*   **Crawling & Deduplication (SQS & Manifest Crawler):** The Manifest Crawler consumes queue messages. It performs lightweight deduplication against state manifests stored in S3, avoiding expensive database lookups. New or updated content is saved to raw storage (S3).
*   **Processing (Worker Lambda):** An S3 event trigger initiates processing. The Worker Lambda chunks the raw content, generates embeddings using Amazon Bedrock, and persists these to the Qdrant vector database.
*   **Tracking (DynamoDB):** Monitors the synchronization state of ingestion jobs.

## Architectural Design Principles

The platform's design is driven by the following core priorities:

*   **Decoupled Dependencies:** To minimize Lambda cold-starts and footprint, the pipeline avoids heavy dependencies (e.g., LangChain, FastEmbed). It uses lightweight custom splitters and direct REST integrations.
*   **Cost-Optimized Deduplication:** Utilizing S3-based manifests significantly reduces the cost of DynamoDB read operations during high-volume ingestion.
*   **Fault Tolerance:** SQS serves as a buffer between crawling and processing, with Dead-Letter Queues (DLQ) isolating failed tasks.

## Key Decisions

This architecture is governed by specific decisions:
*   **SQS Fan-Out:** Enables parallel crawling and improved throughput.
*   **Server-Side Inference:** Offloads intensive vector operations (e.g., BM25) to the Qdrant service.
