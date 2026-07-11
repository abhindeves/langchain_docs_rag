# OpenWiki Documentation Plan

This plan outlines the documentation to be generated for the Serverless RAG Platform.

## Directory Structure

```
/openwiki
|-- _plan.md
|-- quickstart.md
|-- architecture
|   `-- overview.md
|-- services
|   |-- ingestion.md
|   `-- api.md
`-- deployment
    `-- iac.md
```

## Page Content

### `/openwiki/quickstart.md`

*   **Source Evidence:** `/README.md`
*   **Content:**
    *   High-level overview of the project.
    *   Key features and technology stack.
    *   Links to more detailed documentation pages.

### `/openwiki/architecture/overview.md`

*   **Source Evidence:** `/docs/adr/`, `/README.md`
*   **Content:**
    *   Detailed explanation of the event-driven architecture.
    *   Diagrams from `/docs/assets/`.
    *   Summaries of key architectural decisions from the ADRs.

### `/openwiki/services/ingestion.md`

*   **Source Evidence:** `/services/indexer-service/`, `/docs/adr/0001-manifest-crawler-sqs-fanout.md`
*   **Content:**
    *   Detailed description of the ingestion pipeline.
    *   Explanation of the manifest crawler, SQS fanout, and deduplication logic.
    *   Key source files and their roles.

### `/openwiki/services/api.md`

*   **Source Evidence:** `/services/api-service/`
*   **Content:**
    *   Overview of the FastAPI-based API service.
    *   Description of the available endpoints (chat, retrieval).
    *   Configuration and setup.

### `/openwiki/deployment/iac.md`

*   **Source Evidence:** `/infra/`
*   **Content:**
    *   Explanation of the Pulumi-based Infrastructure as Code setup.
    *   Overview of the AWS resources managed by Pulumi.
    *   Instructions for deploying the infrastructure.

## Next Steps

1.  Create the directory structure.
2.  Populate each page with content based on the source evidence.
3.  Delete this plan file.
