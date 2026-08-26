---
type: concept
title: Infrastructure as Code
description: Guide to managing AWS infrastructure using Pulumi for the RAG ingestion system.
tags: [infrastructure, pulumi, aws]
verified:
  - by: openwiki/0.4.0
    at: 2026-08-26T08:35:55.733Z
sources:
  - id: openwiki-source-45429c71bab6f9779e370ede
    resource: repo://infra/__main__.py
  - id: openwiki-source-862443b88cee5adeb9e4ba55
    resource: repo://infra/README.md
generated: {by: "openwiki/0.4.0", at: "2026-08-26T08:35:55.733Z"}
---

# Infrastructure as Code (IaC)

The system utilizes [Pulumi](https://www.pulumi.com/) to define, deploy, and manage AWS infrastructure as code using Python. This approach ensures that our infrastructure state is version-controlled, reproducible, and integrated with the application's lifecycle.

## Overview

Infrastructure resources are located in the `/infra/` directory. The primary entry point for the Pulumi program is `__main__.py`, which declares the necessary AWS resources, including storage, messaging, and database components.

## Pulumi Setup

### State Management
Pulumi tracks the state of your infrastructure in a backend. When working with the Pulumi CLI, it will automatically manage state to ensure that subsequent `pulumi up` executions compute the correct delta between your desired configuration and the actual state in AWS.

### Connecting to AWS
The infrastructure code relies on the standard AWS provider. Credentials should be configured in your environment (e.g., via `aws configure` or standard AWS environment variables).

To manage infrastructure, navigate to the `/infra/` directory:

```bash
cd /infra/
```

### Common Commands

- **Preview changes:** View what Pulumi plans to create, update, or destroy.
  ```bash
  pulumi preview
  ```
- **Deploy infrastructure:** Apply the current `__main__.py` definitions to your AWS account.
  ```bash
  pulumi up
  ```
- **Destroy infrastructure:** Remove all resources managed by the stack.
  ```bash
  pulumi destroy
  ```

## Adding New Resources

To extend the infrastructure, update `/infra/__main__.py`.

1. **Import** the necessary Pulumi AWS classes.
2. **Define** the resource using the Pulumi Python SDK.
3. **Configure** tags consistently with existing resources (e.g., `Project: "rag-ingestion"`).

Example of defining a new resource:

```python
# Add to __main__.py
my_resource = aws.s3.Bucket(
    "new-resource-name",
    tags={
        "Environment": "dev",
        "Project": "rag-ingestion",
    },
)
```

## Infrastructure Components

The infrastructure currently manages several core components:

*   **DynamoDB Table:** `DocumentSyncStatus` tracks ingestion tasks.
*   **S3 Bucket:** `rag-document-store` holds ingested documents.
*   **SQS Queues:** Multiple queues for ingestion and crawler tasks, including Dead-Letter Queues (DLQs) for error handling and visibility timeout configurations.
