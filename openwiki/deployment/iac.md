---
type: Deployment Guide
title: Deployment and Infrastructure as Code (IaC)
description: Guide for deploying and managing the Serverless RAG Platform infrastructure using Pulumi.
tags: [deployment, pulumi, iac, aws]
---

# Deployment and Infrastructure as Code (IaC)

This project uses [Pulumi](https://www.pulumi.com/) to manage all AWS infrastructure as code. The entire stack, from S3 buckets to Lambda functions, is defined in Python, enabling version-controlled, repeatable deployments.

## Infrastructure Overview

The Pulumi program, located in the `/infra` directory, provisions the following key AWS resources:

*   **Amazon DynamoDB:** A `DocumentSyncStatus` table is created to track the state of each document throughout the ingestion pipeline. This table uses a `doc_id` as its primary key and operates in `PAY_PER_REQUEST` billing mode for cost efficiency.
*   **Amazon S3:** An S3 bucket (`rag-document-store`) is provisioned to store raw and processed documents.
*   **Amazon SQS:**
    *   **Crawler Queue:** An SQS queue (`rag-crawler-queue`) with an associated Dead-Letter Queue (DLQ) is set up to manage the crawling of individual URLs. This decouples the master crawler from the individual worker crawlers.
    *   **Ingestion Queue:** Another SQS queue and DLQ (`rag-ingestion-queue`) are used to manage the processing of documents after they have been crawled and uploaded to S3.
*   **AWS Lambda:** The Pulumi script defines the necessary Lambda functions for the master crawler, manifest crawler, and the s3 event worker. It sets up their execution roles, permissions, environment variables, and event source mappings (e.g., connecting a Lambda to an SQS queue or an S3 bucket event).
*   **IAM Roles and Policies:** Pulumi creates the necessary IAM roles and policies to grant the Lambda functions the permissions they need to access other AWS resources like S3, SQS, DynamoDB, and Bedrock.
*   **Amazon EventBridge:** A scheduled rule is created to trigger the master crawler Lambda function on a daily cron schedule.

### Source Files

*   **[`infra/__main__.py`](../../infra/__main__.py):** This is the main entry point for the Pulumi program. It contains the definitions for all the AWS resources listed above.
*   **[`infra/Pulumi.yaml`](../../infra/Pulumi.yaml):** The project file for the Pulumi application.
*   **[`infra/Pulumi.dev.yaml`](../../infra/Pulumi.dev.yaml):** Stack-specific configuration for the `dev` environment.

## Deployment

To deploy the infrastructure, you can use the Pulumi CLI. The general steps are outlined in the [`infra/README.md`](../../infra/README.md) file and involve:

1.  **Initializing the project:** `pulumi new aws-python`
2.  **Previewing changes:** `pulumi preview`
3.  **Deploying the stack:** `pulumi up`

This IaC setup ensures that the entire RAG platform can be deployed, updated, and torn down in a consistent and automated manner.
