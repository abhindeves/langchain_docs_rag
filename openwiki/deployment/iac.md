---
type: Deployment Guide
title: Infrastructure as Code Operations
description: Operational overview of managing AWS infrastructure using Pulumi for the Serverless RAG Platform.
tags: [deployment, pulumi, iac, aws, operations]
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

# Infrastructure as Code Operations

This project utilizes [Pulumi](https://www.pulumi.com/) to manage the lifecycle of all AWS infrastructure. By defining resources as code in Python, we achieve repeatable, version-controlled, and automated cloud deployments.

## IaC Management with Pulumi

Our IaC strategy focuses on declarative resource management, where the desired state of the infrastructure is described in the `/infra` directory.

### State Management
Pulumi maintains a "state file" that maps our code definitions to the actual physical resources in AWS.
*   **Default Behavior:** By default, Pulumi stores this state in the [Pulumi Service](https://www.pulumi.com/docs/intro/pulumi-service/), which provides a managed backend for state concurrency locking and history tracking.
*   **Operational Note:** It is critical to ensure that state remains synchronized. Never manually modify AWS resources created by Pulumi via the AWS Console, as this leads to "configuration drift," where the actual infrastructure state diverges from the code.

### Provisioning Workflow
The provisioning lifecycle follows a standard pattern:

1.  **Change Definition:** Developers modify resources in [`infra/__main__.py`](../../infra/__main__.py).
2.  **Preview (`pulumi preview`):** Evaluates the differences between the current state and the proposed configuration. This step is essential for security auditing, as it highlights destructive changes (e.g., replacing a DynamoDB table).
3.  **Deployment (`pulumi up`):** Applies the changes to the AWS environment. Pulumi calculates the dependency graph and executes create, update, or delete operations in the correct order.

## Infrastructure Components

The infrastructure is modularized into defined AWS resources:

*   **Persistence:** Amazon DynamoDB (`DocumentSyncStatus` table) maintains the ingestion state.
*   **Storage:** Amazon S3 (`rag-document-store`) holds source and processed documents.
*   **Messaging:** SQS queues (`rag-ingestion-queue`, `rag-crawler-queue`) facilitate asynchronous task decoupling, complete with Dead-Letter Queues (DLQ) for error handling.
*   **Compute:** AWS Lambda functions are managed with specific execution roles and event source mappings.
*   **Orchestration:** Amazon EventBridge rules provide serverless task scheduling.

## Managing Configurations
Environment-specific settings (like region or variable overrides) are managed through Pulumi stack configuration files:
*   `infra/Pulumi.yaml`: Global project configuration.
*   `infra/Pulumi.dev.yaml`: Stack-specific overrides for the development environment.

For further details on operational commands, refer to [`infra/README.md`](../../infra/README.md).
