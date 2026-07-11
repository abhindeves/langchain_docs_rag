# Architecture Overview

This document provides a detailed overview of the Serverless RAG Platform's architecture, including the event-driven ingestion pipeline and key design decisions.

## System Architecture

The platform is built on a decoupled, event-driven architecture that leverages AWS serverless components to achieve high scalability, resilience, and cost-efficiency.

![Architecture Diagram](../assets/adr_01.png)

The core components of the architecture are:

*   **EventBridge Scheduler:** A daily cron job that triggers the ingestion process.
*   **Master Crawler Lambda:** A lightweight Lambda function responsible for identifying the target URLs to be crawled and pushing them as messages to an SQS queue.
*   **SQS Queues:**
    *   `rag-crawler-queue`: The main queue for crawling tasks. Messages in this queue trigger the Manifest Crawler Lambda.
    *   `rag-crawler-dlq`: A dead-letter queue to store messages that fail processing after multiple retries, preventing infinite loops and isolating problematic URLs.
*   **Manifest Crawler Lambda:** A Lambda function that processes crawl tasks from the SQS queue. It handles fetching content, deduplication, and storing raw data in S3.
*   **Amazon S3:** Used for storing raw crawled content and state manifests for deduplication.
*   **Amazon DynamoDB:** Tracks the synchronization status of documents.
*   **Amazon Bedrock:** Provides text embedding models.
*   **Qdrant Cloud:** A managed vector database for storing and querying document embeddings.

## Key Architectural Decisions

The architecture of this platform has been shaped by several key decisions, as detailed in the following Architectural Decision Records (ADRs).

### ADR 0001: SQS Fan-Out and S3 Manifest-Based Deduplication

To ensure scalability and cost-efficiency, the ingestion pipeline was designed to be event-driven and to minimize expensive database operations.

*   **Problem:** The initial synchronous crawler was not scalable and incurred high DynamoDB read costs for deduplication.
*   **Solution:** An SQS fan-out pattern was implemented. A master crawler Lambda publishes URLs to an SQS queue, which in turn triggers multiple worker Lambdas. Deduplication is handled by maintaining a manifest file in S3 for each crawl target, which is much cheaper than performing key-by-key lookups in DynamoDB.
*   **Outcome:** This design significantly reduced DynamoDB read costs, improved scalability by enabling parallel processing, and increased resilience through the use of a dead-letter queue.

*Reference: [`docs/adr/0001-manifest-crawler-sqs-fanout.md`](../../docs/adr/0001-manifest-crawler-sqs-fanout.md)*

### ADR 0002: Decoupled Ingestion Dependencies

The ingestion Lambda functions were optimized for performance and size by removing heavy third-party libraries.

*   **Problem:** Dependencies on libraries like LangChain and FastEmbed resulted in large Lambda deployment packages, slow cold starts, and high memory usage.
*   **Solution:**
    *   LangChain's text splitters were replaced with custom, lightweight Python implementations.
    *   Client-side sparse vector generation with FastEmbed was replaced by leveraging Qdrant's server-side BM25 inference.
    *   The official `qdrant-client` SDK was replaced with a minimal, direct REST API client.
*   **Outcome:** This decoupling led to a >99% reduction in the Lambda package size and cold start latency, as well as a >90% reduction in memory footprint. This makes the ingestion pipeline more scalable and cost-effective.

*Reference: [`docs/adr/0002-decouple-ingestion-dependencies.md`](../../docs/adr/0002-decouple-ingestion-dependencies.md)*
