---
type: Concept
title: Infrastructure as Code
description: Overview of the Pulumi-based infrastructure-as-code (IaC) practices for managing the Serverless RAG Platform's AWS environment.
tags: [deployment, pulumi, iac, aws, operations]
verified:
  - by: openwiki/0.5.0
    at: 2026-09-08T12:30:29.951Z
sources:
  - id: openwiki-source-45429c71bab6f9779e370ede
    resource: repo://infra/__main__.py
  - id: openwiki-source-862443b88cee5adeb9e4ba55
    resource: repo://infra/README.md
generated: { by: "openwiki/0.5.0", at: "2026-09-08T12:30:29.951Z" }
---

# Infrastructure as Code

This project utilizes [Pulumi](https://www.pulumi.com/) to manage the lifecycle of the AWS infrastructure. By defining resources as code in Python, the system ensures repeatable, version-controlled, and automated cloud deployments.

## IaC Management

The infrastructure is defined declaratively within the `/infra` directory. This approach treats infrastructure as a first-class citizen of the codebase, ensuring that environment configurations and resource definitions are tracked alongside application logic.

### State Management
Pulumi maintains a "state file" that maps code definitions to actual AWS physical resources.
*   **Backend:** By default, state is stored in the [Pulumi Service](https://www.pulumi.com/docs/intro/pulumi-service/), which handles concurrency locking and provides history tracking.
*   **Invariants:** To avoid configuration drift—where manual changes in the AWS Console diverge from the defined code—all infrastructure modifications must be performed through Pulumi.

### Provisioning Lifecycle
Provisioning follows a standard workflow to minimize risk during updates:
1.  **Change Definition:** Resources are modified in `infra/__main__.py`.
2.  **Preview (`pulumi preview`):** Evaluates the delta between current and desired states. This step is critical for auditing potential destructive actions, such as replacing a DynamoDB table or deleting an S3 bucket.
3.  **Deployment (`pulumi up`):** Applies changes, with Pulumi managing resource dependency graphs and execution order.

## Infrastructure Components

The platform's infrastructure is modularized into several core AWS services:

*   **Persistence:** Amazon DynamoDB (`DocumentSyncStatus`) tracks ingestion status.
*   **Storage:** Amazon S3 (`rag-document-store`) acts as the document repository.
*   **Messaging:** SQS queues (`rag-ingestion-queue`, `rag-crawler-queue`) facilitate asynchronous task decoupling, incorporating Dead-Letter Queues (DLQ) for resilient error handling.
*   **Compute:** AWS Lambda functions, managed with specific execution roles and event source mappings.
*   **Orchestration:** Amazon EventBridge rules provide serverless event scheduling.

## Configuration and Operations

Environment-specific settings are managed via Pulumi stack configuration files:
*   `infra/Pulumi.yaml`: Global project metadata.
*   `infra/Pulumi.dev.yaml`: Stack-specific overrides (e.g., region).

For detailed operational commands and troubleshooting, consult `infra/README.md`.
