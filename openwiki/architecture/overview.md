---
type: Architecture Overview
title: System Architecture Overview
description: High-level architectural model of the RAG platform, focusing on the event-driven ingestion pipeline and data lifecycle from raw source to vector store.
tags: [architecture, aws, serverless, rag]
verified:
  - by: openwiki/0.5.0
    at: 2026-09-04T12:25:44.572Z
sources:
  - id: openwiki-source-38f037d212ee358478211ba3
    resource: repo://docs/adr/0001-manifest-crawler-sqs-fanout.md
  - id: openwiki-source-af70149a354536b126186304
    resource: repo://docs/adr/0002-decouple-ingestion-dependencies.md
generated: { by: "openwiki/0.5.0", at: "2026-09-04T12:25:44.572Z" }
---

# System Architecture Overview

This document provides a high-level model of the Serverless RAG Platform's architecture. The system comprises three primary subsystems: the API Service, the Ingestion Pipeline, and the Evaluation Service.

## High-Level Communication Flow

The following diagram illustrates the interaction between the system's core components.

```mermaid
flowchart TB
    API[API Service]
    Ingestion[Ingestion Pipeline]
    Eval[Evaluation Service]
    
    User((User)) --> API
    API --> Ingestion
    API --> Eval
    Ingestion --> Qdrant[(Vector DB)]
    Eval --> Qdrant
```
*System component interaction diagram.*

## Component Responsibilities

*   **API Service:** Acts as the primary entrypoint for users, handling requests and coordinating tasks across the pipeline and evaluation services.
*   **Ingestion Pipeline:** Automates the transformation of external content into searchable vector embeddings.
*   **Evaluation Service:** Assesses the quality and relevance of retrieved content and generated responses against defined benchmarks.

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
