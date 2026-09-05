---
type: concept
title: Infrastructure Architecture
description: Overview of the AWS infrastructure managed by Pulumi for the RAG ingestion system.
tags: [infrastructure, pulumi, aws]
verified:
  - by: openwiki/0.5.0
    at: 2026-09-04T12:25:44.572Z
sources:
  - id: openwiki-source-45429c71bab6f9779e370ede
    resource: repo://infra/__main__.py
  - id: openwiki-source-862443b88cee5adeb9e4ba55
    resource: repo://infra/README.md
generated: { by: "openwiki/0.5.0", at: "2026-09-04T12:25:44.572Z" }
---

# Infrastructure Architecture

The system uses [Pulumi](https://www.pulumi.com/) to manage AWS infrastructure as code using Python. This ensures that infrastructure state is version-controlled, reproducible, and tightly coupled with the application's lifecycle.

## Overview

The infrastructure codebase is located in the `/infra/` directory. The primary entry point for the Pulumi program is `__main__.py`, which declares essential AWS resources including storage, messaging, and database components.

## Environment Management

Environments are managed using Pulumi stacks, which correspond to configuration files (e.g., `Pulumi.dev.yaml`). Each stack maintains its own infrastructure state, allowing for isolated deployments across development, staging, or production environments. 

To manage infrastructure, navigate to the `/infra/` directory:

```bash
cd /infra/
```

### Pulumi Commands

- **Preview changes:** Review proposed changes against the current state.
  ```bash
  pulumi preview
  ```
- **Deploy infrastructure:** Apply the current `__main__.py` definitions to the configured AWS environment.
  ```bash
  pulumi up
  ```
- **Destroy infrastructure:** Remove all resources managed by the current stack.
  ```bash
  pulumi destroy
  ```

## Infrastructure Components

The infrastructure includes several core AWS services:

*   **DynamoDB Table (`DocumentSyncStatus`):** Tracks the status of ingestion tasks using `doc_id` as the hash key.
*   **S3 Bucket (`rag-document-store`):** Serves as the central store for ingested documents.
*   **SQS Queues:** 
    *   **Ingestion Queue:** Processes ingestion tasks, configured with a 900s visibility timeout and a Dead-Letter Queue (DLQ).
    *   **Crawler Queue:** Processes crawler tasks, configured with a 300s visibility timeout and a DLQ.

## Extending Infrastructure

To add or modify resources, update `/infra/__main__.py`:

1.  **Define:** Use the Pulumi AWS Python SDK.
2.  **Tagging:** Always apply consistent tags (e.g., `{"Environment": "dev", "Project": "rag-ingestion"}`) to ensure cost tracking and resource management.
3.  **Validate:** Run `pulumi preview` to verify that the changes meet the desired state before applying.
