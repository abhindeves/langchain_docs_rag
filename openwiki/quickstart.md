---
type: Concept
title: Quickstart
description: Onboarding guide for the RAG platform, covering the architecture, components, and local development environment setup.
tags: [quickstart, onboarding, architecture]
verified:
  - by: openwiki/0.4.0
    at: 2026-08-26T08:35:55.733Z
sources:
  - id: openwiki-source-45429c71bab6f9779e370ede
    resource: repo://infra/__main__.py
  - id: openwiki-source-b6f4e31ca8dfe49b64742655
    resource: repo://services/api-service/pyproject.toml
generated: {by: "openwiki/0.4.0", at: "2026-08-26T08:35:55.733Z"}
---

# Quickstart

Welcome to the RAG (Retrieval-Augmented Generation) Platform. This guide helps you understand our serverless architecture and set up your local development environment.

## Architecture Overview

Our platform is a production-grade, event-driven system built on AWS using a serverless-first approach. It is designed to be highly scalable, decoupled, and cost-efficient.

### Key Components

*   **[System Architecture Overview](./architecture/overview.md):** The high-level design and data flow.
*   **[Infrastructure as Code](./architecture/infrastructure.md):** Managed using [Pulumi](https://www.pulumi.com/) with Python.
*   **[Ingestion Pipeline](./architecture/ingestion-pipeline.md):** Processes documents asynchronously via SQS and AWS Lambda, leveraging Amazon Bedrock for embeddings and storing vectors in Qdrant.
*   **[API Service](./architecture/api-service.md):** The FastAPI-based interface for handling search and retrieval requests.

## Getting Started

### Prerequisites

1.  **AWS CLI:** [Configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html) with appropriate credentials.
2.  **Pulumi:** [Installed](https://www.pulumi.com/docs/get-started/install/) and authenticated.
3.  **Python 3.11+:** Required for Lambda functions and IaC scripts.
4.  **Docker:** Required for local testing of services and vector database containers.

### Local Environment Setup

1.  **Clone the Repository:**
    ```bash
    git clone <repository-url>
    cd rag-platform
    ```

2.  **Install Dependencies:**
    We use `poetry` for dependency management.
    ```bash
    poetry install
    ```

3.  **Environment Configuration:**
    Copy the sample configuration and update the necessary AWS and Qdrant credentials.
    ```bash
    cp .env.example .env
    ```

4.  **Initialize Infrastructure:**
    Use Pulumi to preview/deploy infrastructure (requires configured AWS access):
    ```bash
    pulumi up
    ```

## Development Workflow

*   **Testing:** We follow a standardized [Testing Strategy](./testing/strategy.md). Run unit and integration tests using `pytest`.
*   **Documentation:** Updates to this wiki are handled via GitHub Actions as documented in the deployment guide.
