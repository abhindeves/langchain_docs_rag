# Collaborative RAG Platform Monorepo Implementation Plan

This plan is structured for **collaborative, phase-by-phase development**. Instead of the AI generating the entire codebase, we will walk through the implementation step-by-step. For each step, you will lead the coding/execution, and I will provide code patterns, structure guidance, review, and troubleshooting support.

---

## Developer-Agent Collaboration Model

For each step:
1. **Goal**: The objective of the step.
2. **User Action**: The files you will create or modify, and commands you will run.
3. **Agent Guidance**: The architectural templates, configurations, or coding patterns I will provide to help you.
4. **Checkpoint**: The exact command or test to run to verify that step is fully working before moving to the next one.

---

## Phase-by-Phase Roadmap

### Phase 1: Local Foundation (Docker Compose & Health Checks)
**Objective**: Set up the monorepo root workspace, a FastAPI service skeleton, a local Qdrant instance, and verify local container networking.

#### Step 1.1: Monorepo Root & Workspace Setup
- **Goal**: Initialize the project structure and configure the package manager (`uv` workspace or equivalent).
- **User Action**:
  - Set up a root `pyproject.toml` declaring a workspace with `./libs/shared-lib` and `./services/api-service`.
  - Create the folder structure:
    ```
    ├── libs/shared-lib/
    ├── services/api-service/
    └── infra/local/
    ```
- **Agent Guidance**: Provide a minimal root `pyproject.toml` workspace template.
- **Checkpoint**: Run `uv sync` or dependency install to ensure workspace resolution succeeds without errors.

#### Step 1.2: Docker Compose Setup
- **Goal**: Orchestrate Qdrant and the API service skeleton locally.
- **User Action**: Create the root `docker-compose.yml` and API service `Dockerfile`.
- **Agent Guidance**: Provide a `docker-compose.yml` configuration defining ports, volumes, and shared docker network, and a multi-stage `Dockerfile` optimized for FastAPI.
- **Checkpoint**: Run `docker compose up --build -d qdrant` to verify Qdrant is running on `http://localhost:6333`.

#### Step 1.3: Health Check Endpoints
- **Goal**: Establish the API service with health and readiness checks.
- **User Action**:
  - Implement a basic FastAPI app in `services/api-service/src/main.py`.
  - Create `/health/liveness` and `/health/readiness` endpoints.
- **Agent Guidance**: Provide patterns for asynchronous check of Qdrant connection via the `qdrant-client` library in the readiness handler.
- **Checkpoint**: Query `http://localhost:8000/health/readiness` using `curl` and receive `{"status": "ready"}`.

---

### Phase 2: Shared Library & Indexer Service
**Objective**: Build document parsing, text chunking, and embedding generation inside the indexer, and write results to Qdrant.

#### Step 2.1: Shared Embedding Utilities
- **Goal**: Standardize vector generation so both indexer and API use identical embedding logic.
- **User Action**: Create `libs/shared-lib/src/shared/embeddings.py`.
- **Agent Guidance**: Provide abstract base classes and concrete service implementations (e.g. using OpenAI or AWS Bedrock APIs) to handle request limits and model settings.
- **Checkpoint**: Run a mock verification script to embed a sample sentence and output the vector length.

#### Step 2.2: Document Parser & Chunker
- **Goal**: Read local source documents and partition them into overlapping segments.
- **User Action**: Create `services/indexer-service/src/parser.py` and `chunker.py`.
- **Agent Guidance**: Guide you on chunk size selection, overlapping strategies, and keeping metadata (like source file path and headers) intact.
- **Checkpoint**: Run the parser and chunker on a sample Markdown document and print out the character length and metadata of the first 3 chunks.

#### Step 2.3: Ingestion Runner & DB Sync
- **Goal**: Synchronize generated chunks to the Qdrant vector database.
- **User Action**: Implement the ingestion driver in `services/indexer-service/src/main.py` that upserts chunk records.
- **Agent Guidance**: Help configure vector payload structures and upsert calls using Qdrant collection schemas.
- **Checkpoint**: Ingest a folder of text documents, and query Qdrant's `/collections/{collection_name}` HTTP endpoint to verify count of inserted points.

#### Step 2.4: Incremental Indexing Strategy
- **Goal**: Prevent reprocessing unchanged files by implementing state-tracking.
- **User Action**: Create `services/indexer-service/src/incremental.py` to calculate file hashes and keep a lightweight state database (or local JSON state).
- **Agent Guidance**: Design logic to compare current file hashes against the database, purging deleted files from Qdrant and only chunking/embedding modified files.
- **Checkpoint**: Run the indexer twice. Confirm the second run does zero embeddings and updates nothing. Make a small edit to one document and verify only that file gets reindexed.

---

### Phase 3: Secure Retrieval & Chat Endpoints
**Objective**: Enable JWT protection on the API, perform semantic search queries, assemble prompting context, and stream model generations.

#### Step 3.1: JWT Authentication & Middleware
- **Goal**: Protect API endpoints using token validation and correlation tracking.
- **User Action**: Create JWT middleware in the FastAPI API service and configure correlation IDs for structured logs.
- **Agent Guidance**: Provide clean FastAPI dependencies for token decoding, validation, and role extraction, alongside structured logging configurations.
- **Checkpoint**: Send a request without a token to `/api/v1/retrieve` and verify it returns a `401 Unauthorized` response.

#### Step 3.2: Retrieval Endpoint
- **Goal**: Expose a secure endpoint that searches Qdrant for semantic relevance.
- **User Action**: Implement the `/api/v1/retrieve` route.
- **Agent Guidance**: Assist in embedding the user query and fetching top-K items from Qdrant, filtering by similarity threshold and returning structured payloads.
- **Checkpoint**: Send a valid query using a testing script and verify you receive matching text chunks along with metadata and similarity scores.

#### Step 3.3: Context Prompting & Chat Generation
- **Goal**: Build the conversational API context and stream LLM outputs.
- **User Action**: Implement the `/api/v1/chat` endpoint.
- **Agent Guidance**: Provide prompt templates designed to prevent hallucinations and structural suggestions for handling session chat history and streaming responses.
- **Checkpoint**: Invoke `/api/v1/chat` with a question, and receive a completed response referencing specific source document chunks.

---

### Phase 4: Evaluation Service
**Objective**: Implement offline evaluations to track changes in retrieval and generation quality objectively.

#### Step 4.1: Retrieval Performance Metrics
- **Goal**: Measure retrieval efficiency on a golden dataset.
- **User Action**: Create the golden dataset JSON file and implement `services/evaluation-service/src/metrics.py`.
- **Agent Guidance**: Provide mathematical/code implementations for Precision@K, Recall@K, Mean Reciprocal Rank (MRR), and NDCG.
- **Checkpoint**: Run evaluation on a test dataset and output a structured report showing retrieval scores.

#### Step 4.2: Generation Evaluation (Ragas)
- **Goal**: Use LLM-as-a-judge to test faithfulness and relevance of generation.
- **User Action**: Create `services/evaluation-service/src/evaluator.py` running Ragas metrics.
- **Agent Guidance**: Show how to configure the Ragas evaluator and log metrics to files for regression testing.
- **Checkpoint**: Execute the evaluation suite offline and verify generation quality metrics are generated without errors.

---

### Phase 5: AWS Cloud Migration (EC2 & Docker Compose)
**Objective**: Deploy the local container layout onto AWS EC2 with a Nginx reverse proxy and SSL.

#### Step 5.1: Production Docker Compose & Nginx Setup
- **Goal**: Secure and wrap local API endpoints with Nginx inside a production compose file.
- **User Action**: Create `infra/aws/nginx.conf` and `docker-compose.prod.yml`.
- **Agent Guidance**: Provide safe Nginx reverse proxy rules, rate-limiting directives, and configurations for Let's Encrypt SSL.
- **Checkpoint**: Run a local check using the production configuration and ensure Nginx proxy routes traffic to the API container.

#### Step 5.2: EC2 Deployment Guide
- **Goal**: Run the Docker Compose stack on an AWS EC2 instance.
- **User Action**: Set up the security groups, provision the instance, clone the repository, and spin up the services.
- **Agent Guidance**: Walk you through setup steps, secure SSH practices, and debugging connectivity issues.
- **Checkpoint**: Access the API service securely over HTTPS using your custom domain.

---

## Verification Strategy

- **Automated Verification**: We will create lightweight pytest files for services inside `./tests` directories to run unit checks.
- **Integration Verification**: Use python scripts utilizing `httpx` or curl to verify inter-container networking inside the compose setup.
