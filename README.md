# Serverless RAG Platform

A production-grade, event-driven Retrieval-Augmented Generation (RAG) platform deployed entirely on AWS using serverless architecture and Infrastructure as Code.

## Architecture Highlights
* **Event-Driven Ingestion:** Highly decoupled architecture utilizing Amazon SQS to trigger asynchronous, auto-scaling Lambda workers.
* **Intelligent Deduplication:** DynamoDB state tracking with MD5/SHA256 content hashing to prevent redundant LLM embedding costs for unchanged documents.
* **High-Performance Embeddings:** Integrated with Amazon Bedrock (`amazon.titan-embed-text-v2:0`) via an asynchronous Boto3 client.
* **Vector Storage:** Qdrant Cloud configured for both dense (Cosine) and sparse (BM25) hybrid vectors.
* **Infrastructure as Code (IaC):** 100% of the AWS infrastructure (S3, SQS, DynamoDB, Lambda, IAM) is managed programmatically via Pulumi Python.

## Tech Stack
- **Compute:** AWS Lambda, Amazon SQS
- **State & Storage:** Amazon DynamoDB, Amazon S3
- **AI/ML:** Amazon Bedrock (Titan Embeddings)
- **Vector DB:** Qdrant Cloud
- **IaC & CI/CD:** Pulumi (Python), GitHub Actions
- **API Framework:** FastAPI, Uvicorn

## Roadmap
- [x] **Phase 1: Ingestion Pipeline** - Crawler, SQS queues, deduplication, and Bedrock embedding workers.
- [ ] **Phase 2: API Service** - FastAPI endpoints for hybrid (dense + sparse) semantic search.
- [ ] **Phase 3: Evaluation Service** - RAG metric evaluation and continuous quality monitoring.
