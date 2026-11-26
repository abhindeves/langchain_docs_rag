---
type: Architecture Overview
title: System Architecture Overview
description: High-level architectural model of the RAG platform, focusing on the event-driven ingestion pipeline and data lifecycle from raw source to vector store.
tags: [architecture, aws, serverless, rag]
verified:
  - by: openwiki/0.9.0
    at: 2026-11-26T18:01:40.921Z
sources:
  - id: openwiki-source-38f037d212ee358478211ba3
    resource: repo://docs/adr/0001-manifest-crawler-sqs-fanout.md
  - id: openwiki-source-af70149a354536b126186304
    resource: repo://docs/adr/0002-decouple-ingestion-dependencies.md
  - id: openwiki-source-c8424396153b7ec9abf7e07d
    resource: repo://services/api-service/src/api/main.py
  - id: openwiki-source-0d7d57bc9732734adbf29b14
    resource: repo://services/indexer-service/src/indexer/lambda_handler.py
  - id: openwiki-source-53309d3d93deed43bfcac7af
    resource: repo://services/indexer-service/src/indexer/manifest_crawler.py
generated: { by: "openwiki/0.9.0", at: "2026-11-26T18:01:40.921Z" }
---

# System Architecture Overview

This document provides a high-level model of the RAG platform's architecture. The system comprises three primary subsystems: the API Service, the Ingestion Pipeline (powered by the Indexer Service), and the Evaluation Service.

## High-Level Communication Flow

The system components interact as follows:

```mermaid
flowchart TB
    User((User)) --> API[API Service]
    API --> Indexer[Indexer Service]
    API --> Eval[Evaluation Service]
    Indexer --> Qdrant[(Vector DB)]
    Eval --> Qdrant
    Eval --> Indexer
```
*System component interaction diagram.*

## Component Responsibilities

*   **API Service:** Acts as the primary entrypoint for users, exposing endpoints for document ingestion, retrieval, and evaluation requests.
*   **Indexer Service:** Manages the ingestion pipeline, orchestrating crawling, document processing, and vector storage updates in Qdrant.
*   **Evaluation Service:** Assesses retrieval and generation quality by querying the vector database and invoking the indexer for benchmarking tasks.

## Data Lifecycle and Control Flow

The platform relies on an event-driven flow for document ingestion, managed primarily by the Indexer Service.

```mermaid
flowchart LR
    EB[EventBridge] --> MC[Master Crawler]
    MC --> Q[SQS Queue]
    Q --> ManC[Manifest Crawler]
    ManC --> S3Raw[(S3 Raw Storage)]
    S3Raw --> S3Trigger[S3 Event Trigger]
    S3Trigger --> Worker[Indexer Worker]
    Worker --> Bedrock[Amazon Bedrock]
    Worker --> Qdrant[(Qdrant Vector DB)]
    Worker --> DDB[(DynamoDB Status)]
```
*Ingestion lifecycle flow managed by the Indexer Service.*

### Subsystem Details

*   **Indexer Service Orchestration:** The Indexer uses a fan-out pattern starting with an EventBridge trigger, followed by crawling and deduplication against S3 manifests. The Worker Lambda performs chunking and embedding before final persistence in Qdrant.
*   **API Service Coordination:** The API service acts as a mediator, receiving user commands and delegating heavy lifting to either the Indexer (for document operations) or the Evaluation Service (for benchmarking).
*   **Evaluation Service Interaction:** The Evaluation service performs read-only access to the Vector DB and can trigger re-indexing or status updates via the Indexer Service.

## Architectural Design Principles

The platform's design is driven by the following core priorities:

*   **Decoupled Services:** Services interact via defined interfaces, allowing independent scaling and deployment.
*   **Event-Driven Pipeline:** The Indexer Service relies on asynchronous queues (SQS) to manage throughput and ensure fault tolerance.
*   **Optimized Storage:** Usage of S3-based manifests and Qdrant ensures efficient handling of vector data and metadata.
*   **Minimalist Dependency Footprint:** Services avoid bloated libraries to minimize cold-starts and runtime overhead.
