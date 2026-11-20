---
type: concept
title: Infrastructure Architecture
description: Overview of the AWS infrastructure managed by Pulumi, including core storage, messaging, and compute resources.
tags: [infrastructure, pulumi, aws]
verified:
  - by: openwiki/0.9.0
    at: 2026-11-20T16:35:37.158Z
sources:
  - id: openwiki-source-45429c71bab6f9779e370ede
    resource: repo://infra/__main__.py
  - id: openwiki-source-862443b88cee5adeb9e4ba55
    resource: repo://infra/README.md
generated: { by: "openwiki/0.9.0", at: "2026-11-20T16:35:37.158Z" }
---

# Infrastructure Architecture

The platform uses [Pulumi](https://www.pulumi.com/) to define, manage, and provision AWS infrastructure as code using Python. By managing infrastructure through code, the system ensures that environments are reproducible, version-controlled, and closely coupled with the application's lifecycle.

## Overview

The infrastructure codebase resides in the `/infra/` directory. The primary entry point for the Pulumi program is `repo://infra/__main__.py`, which declares core AWS services required by the platform.

## Infrastructure Management

Environments are defined as Pulumi stacks (e.g., `Pulumi.dev.yaml`). Each stack maintains independent state, enabling safe and isolated deployments across development, testing, and production environments.

To interact with the infrastructure:

1.  Navigate to the `/infra/` directory:
    ```bash
    cd /infra/
    ```
2.  Use the [Pulumi CLI](https://www.pulumi.com/docs/cli/) to manage lifecycle events:
    *   `pulumi preview`: Compare local definitions against current cloud state.
    *   `pulumi up`: Provision or update infrastructure to match the desired state.
    *   `pulumi destroy`: Remove resources managed by the stack.

## Key Resources

The `/infra/__main__.py` file manages several critical AWS resources:

*   **Compute:** 
    *   `worker_lambda`: Processes tasks from the Ingestion Queue.
    *   `manifest_crawler_lambda`: Processes crawler tasks.
    *   `master_crawler_lambda`: Orchestrates periodic crawling schedules.
*   **Storage:**
    *   **DynamoDB (`DocumentSyncStatus`):** Tracks ingestion status and synchronization states.
    *   **S3 Bucket (`rag-document-store`):** The primary repository for ingested documents.
*   **Messaging (SQS):**
    *   **Ingestion Queue:** Manages ingestion workloads; utilizes a 900s visibility timeout and a Dead-Letter Queue (DLQ).
    *   **Crawler Queue:** Manages crawling workloads; utilizes a 300s visibility timeout and a DLQ.

## Extension and Maintenance

To modify or extend the platform's infrastructure:

1.  **Define:** Add resources within `repo://infra/__main__.py` using the `pulumi_aws` SDK.
2.  **Tag:** Apply consistent resource tags (e.g., `Environment`, `Project`) to facilitate cost tracking and resource lifecycle management.
3.  **Validate:** Always execute `pulumi preview` before applying changes to ensure the plan matches intended modifications.
