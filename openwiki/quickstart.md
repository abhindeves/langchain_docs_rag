---
type: Concept
title: Quickstart
description: Central entry point for developers, outlining the RAG platform architecture, repository structure, and local development workflows.
tags: [quickstart, onboarding, architecture]
verified:
  - by: openwiki/0.5.0
    at: 2026-09-04T12:25:44.572Z
sources:
  - id: openwiki-source-45429c71bab6f9779e370ede
    resource: repo://infra/__main__.py
  - id: openwiki-source-b6f4e31ca8dfe49b64742655
    resource: repo://services/api-service/pyproject.toml
generated: { by: "openwiki/0.5.0", at: "2026-09-04T12:25:44.572Z" }
---

# Quickstart

Welcome to the RAG (Retrieval-Augmented Generation) Platform. This guide provides a central entry point for developers to understand our serverless-first architecture, service documentation, and standard operating procedures.

## Architecture Overview

Our platform is a production-grade, event-driven system built on AWS using a serverless-first approach. It is designed to be highly scalable, decoupled, and cost-efficient.

*   [System Overview](./architecture/overview.md)
*   [API Service Architecture](./architecture/api-service.md)
*   [Ingestion Pipeline Architecture](./architecture/ingestion-pipeline.md)
*   [Infrastructure Architecture](./architecture/infrastructure.md)

## Service Documentation

*   [API Service Reference](./services/api.md)
*   [Ingestion Service Reference](./services/ingestion.md)

## Development and Deployment

*   [Testing Strategy](./testing/strategy.md)
*   [Infrastructure as Code Operations](./deployment/iac.md)
*   [CI/CD Workflows](./deployment/github-actions.md)

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
