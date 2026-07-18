---
type: Quickstart Guide
title: Quickstart - Serverless RAG Platform
description: High-level overview and getting started guide for the Serverless RAG Platform on AWS.
tags: [quickstart, overview, aws, rag, serverless]
---

# Quickstart: Serverless RAG Platform

This document provides a high-level overview of the Serverless RAG Platform, a production-grade, event-driven Retrieval-Augmented Generation (RAG) platform deployed entirely on AWS.

## Overview

The platform is designed with a serverless-first approach, leveraging AWS services to create a scalable, decoupled, and cost-efficient system for RAG. The entire infrastructure is managed programmatically using Pulumi, enabling easy deployment and maintenance.

### Key Features

*   **Event-Driven Ingestion:** A highly decoupled architecture using Amazon SQS to trigger asynchronous, auto-scaling Lambda workers for document processing and embedding.
*   **Intelligent Deduplication:** Utilizes DynamoDB and content hashing (MD5/SHA256) to track document state and avoid redundant embedding costs for unchanged content.
*   **High-Performance Embeddings:** Integrates with Amazon Bedrock for efficient text embeddings.
*   **Hybrid Vector Storage:** Leverages Qdrant Cloud for storing both dense and sparse vectors to enable hybrid search.
*   **Infrastructure as Code (IaC):** All AWS infrastructure is managed via Pulumi with Python.

## Tech Stack

*   **Compute:** AWS Lambda, Amazon SQS
*   **State & Storage:** Amazon DynamoDB, Amazon S3
*   **AI/ML:** Amazon Bedrock (Titan Embeddings)
*   **Vector DB:** Qdrant Cloud
*   **IaC & CI/CD:** Pulumi (Python), GitHub Actions
*   **API Framework:** FastAPI, Uvicorn

## Documentation Sections

*   **[Architecture Overview](./architecture/overview.md):** A detailed look at the system's architecture and design decisions.
*   **[Ingestion Service](./services/ingestion.md):** Describes the data ingestion pipeline.
*   **[API Service](./services/api.md):** Details on the FastAPI-based query and retrieval endpoints.
*   **[Deployment with IaC](./deployment/iac.md):** Information on deploying and managing the infrastructure with Pulumi.
*   **[GitHub Actions](./deployment/github-actions.md):** Details on the automated documentation update workflow.
