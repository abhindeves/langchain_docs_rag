---
type: concept
title: Infrastructure Architecture
description: Overview of the AWS infrastructure managed by Pulumi for the RAG ingestion system.
tags: [infrastructure, pulumi, aws]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-17T11:55:30.258Z
sources:
  - id: openwiki-source-45429c71bab6f9779e370ede
    resource: repo://infra/__main__.py
  - id: openwiki-source-862443b88cee5adeb9e4ba55
    resource: repo://infra/README.md
generated: { by: "openwiki/0.7.2", at: "2026-10-17T11:55:30.258Z" }
---

# Infrastructure Architecture

The system uses [Pulumi](https://www.pulumi.com/) to manage AWS infrastructure as code using Python, providing a reproducible and version-controlled environment.

## Overview

The infrastructure codebase resides in the `/infra/` directory. The primary entry point is `__main__.py`, where resources are defined using the `pulumi_aws` SDK. 

Pulumi manages dependencies implicitly; when a resource (e.g., an SQS queue) requires an attribute of another (e.g., a DLQ ARN), passing the resource object or its `apply` method ensures the correct creation order. For example, the `redrive_policy` of an SQS queue uses `dlq.arn.apply(...)` to dynamically inject the DLQ's ARN only after it has been created, ensuring robust dependency handling across the stack.

## Environment Management

Environments are managed using Pulumi stacks, mapping to configuration files like `Pulumi.dev.yaml`. Each stack maintains isolated state, supporting distinct deployments for development, staging, or production.

Navigate to `/infra/` to execute commands:

### Pulumi Commands

- **Preview changes:** Review proposed changes against the current state.
  ```bash
  pulumi preview
  ```
- **Deploy infrastructure:** Apply definitions to the configured AWS environment.
  ```bash
  pulumi up
  ```
- **Destroy infrastructure:** Remove all stack-managed resources.
  ```bash
  pulumi destroy
  ```

## Infrastructure Components

Key resources defined in `__main__.py`:

*   **DynamoDB Table (`DocumentSyncStatus`):** Tracks ingestion task status via `doc_id`.
*   **S3 Bucket (`rag-document-store`):** Stores ingested documents.
*   **SQS Queues:**
    *   **Ingestion Queue:** Processes ingestion tasks (900s visibility timeout, DLQ).
    *   **Crawler Queue:** Processes crawler tasks (300s visibility timeout, DLQ).

## Extending Infrastructure

To modify resources:

1.  **Define:** Update `/infra/__main__.py` using the Pulumi AWS Python SDK.
2.  **Tag:** Apply standard tags (`Environment`, `Project`) for cost tracking.
3.  **Validate:** Run `pulumi preview` to verify the desired state before application.
