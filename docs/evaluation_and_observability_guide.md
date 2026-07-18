# RAG Evaluation & Observability Strategy & Study Guide

This document outlines the architecture, frameworks, and metrics required to implement production-grade **Observability (Tracing/Monitoring)** and **Evaluations (Quality Control)** for our serverless RAG platform.

Like the Latency Guide, this is a **collaborative design document**. It provides structural guidelines along with **Study & Homework Assignments** to prompt you to research implementations, make trade-offs, and enrich this document with your findings.

---

## 1. Observability: System & LLM Tracing

### The Production Goal
Implement end-to-end tracing that correlates HTTP client requests with embedding generation, database retrievals, reranker calls, and LLM text completions. We want to trace exactly how a query evolved:

```
[ HTTP Client Request ]
       │ (trace_id: 12345)
       ├──> [ Embedder Client ] ──> (Latency, Input Tokens)
       ├──> [ Qdrant Query ]    ──> (Cosine/Sparse scores, Chunk IDs)
       ├──> [ Bedrock Rerank ]  ──> (Rerank relevance scores)
       └──> [ Bedrock LLM ]     ──> (System prompt, Input/Output Tokens, Generation)
```

We will evaluate **OpenTelemetry (OTel)** for system/FastAPI spans and **Langfuse** (or **Arize Phoenix / LangSmith**) for specialized LLM/RAG application traces.

### 📝 Background Study & Document Enrichment
> [!IMPORTANT]
> **Your Task:** Research how to integrate **Langfuse** or **Arize Phoenix** with a FastAPI application using standard async middleware or custom handlers.
> * Fill out the code snippet below demonstrating how to instrument `llm.invoke` or a router handler to send tracing spans asynchronously.
> * Research how to propagate context/trace headers across services in a python monorepo.

```python
# HOMEWORK: Complete the boilerplate to integrate Langfuse tracing into your chat handler
from langfuse.decorators import observe

# Document how to decorate your retrieval/llm calls:
@observe()
async def retrieve_and_chat(query: str):
    # Your RAG orchestration steps here
    # Explain: How does the decorator capture Qdrant payloads and LLM outputs?
    pass
```

* **Selected LLM Tracing Tool:** *[Choose between Langfuse, Arize Phoenix, or LangSmith and explain why]*
* **Performance Impact:** *[Research: Do these tracers send spans on background threads/queues, or do they block HTTP response times?]*

---

## 2. LLM Metrics & Token/Cost Auditing

### The Production Goal
Extract, parse, and store LLM token usage (`inputTokens`, `outputTokens`) for billing, rate-limiting, and budget auditing per user/tenant.

### 📝 Background Study & Document Enrichment
> [!IMPORTANT]
> **Your Task:** Look up the exact schema of Bedrock's Converse API response (`converse` and `converse_stream` outputs).
> 1. Complete the Python helper function below to extract usage metrics.
> 2. Propose a schema for saving these records to DynamoDB for multi-tenant billing.

```python
# HOMEWORK: Complete this helper to extract token usage from Bedrock Converse API response
def extract_token_usage(converse_response_body: dict) -> dict:
    # Look up the Bedrock documentation for the converse() output dictionary structure.
    # Extract input tokens, output tokens, and calculate estimated cost for Claude 3 Haiku.
    usage = converse_response_body.get("usage", {}) # Verify if this is the correct key

    return {
        "input_tokens": 0,    # Fill in path
        "output_tokens": 0,   # Fill in path
        "total_tokens": 0,    # Fill in path
        "estimated_cost_usd": 0.0 # Haiku pricing: $0.25 / M input, $1.25 / M output
    }
```

#### Proposed Multi-Tenant Billing DynamoDB Schema:
* **Partition Key (PK):** `TENANT#<tenant_id>`
* **Sort Key (SK):** `USAGE#<timestamp>#<correlation_id>`
* **Attributes:** *[List what details you need to audit cost per tenant (e.g., model_id, tokens_in, tokens_out)]*

---

## 3. Offline Evaluations (Pre-Deployment Testing)

### The Production Goal
Establish a continuous integration (CI) quality gate. If a developer changes a prompt, chunking strategy, or retrieval algorithm, we must run automated tests to check for regressions in search accuracy or answer quality before deploying to production.

We will evaluate **Ragas** and **TruLens** as LLM-as-a-judge frameworks.

```
       [ Proposed Prompt Changes ]
                    │
                    ▼
       [ Run Ragas Test Pipeline ]
                    │
   ┌────────────────┴────────────────┐
   ▼                                 ▼
[ Metrics Pass (> 0.85) ]    [ Metrics Fail (< 0.85) ]
   │                                 │
   ▼ (Deploy)                        ▼ (Block Build & Report)
```

### 📝 Background Study & Document Enrichment
> [!IMPORTANT]
> **Your Task:** Research the core RAG evaluation metrics defined by the Ragas framework.
> 1. Define how **Faithfulness**, **Answer Relevance**, and **Context Recall** are computed mathematically or conceptually by an LLM-as-a-judge.
> 2. Complete the Ragas testing script boilerplate below.

* **Faithfulness:** *[Explain how the LLM judge evaluates if the answer is grounded only in the context]*
* **Answer Relevance:** *[Explain how semantic similarity between generated answer and initial query is evaluated]*
* **Context Recall:** *[Explain how the system evaluates if all ground truth information was retrieved]*

```python
# HOMEWORK: Complete the python script to run Ragas evaluations on a small evaluation dataset
from datasets import Dataset
# from ragas import evaluate
# from ragas.metrics import faithfulness, answer_relevance

eval_data = {
    "question": ["What is LangGraph routing?"],
    "contexts": [["Your retrieved documents go here..."]],
    "answer": ["Your generated LLM response goes here..."],
    "ground_truth": ["The reference correct answer from documentation..."]
}

# Create Dataset and write evaluate function.
# Research: Which LLM should act as the evaluator judge (e.g. Claude 3.5 Sonnet)?
```

---

## 4. Online Feedback & Input Guardrails

### The Production Goal
Protect the application from malicious prompts (jailbreaks, prompt injections), redact PII (Personally Identifiable Information) before sending data to LLMs, and collect explicit/implicit user feedback to improve the retrieval corpus.

```
[ User Input ] ──> [ Guardrail Check (PII Redaction/Toxicity) ] ──> [ Safe Prompt ]
                                                                          │
                                                                          ▼
[ User Feedback (Thumbs Up/Down) ] <── [ RAG Pipeline Output ] <─── [ Execute RAG ]
```

### 📝 Background Study & Document Enrichment
> [!IMPORTANT]
> **Your Task:** Research guardrail frameworks (e.g., **AWS Bedrock Guardrails**, **NeMo Guardrails**, or writing regex-based PII scrubbers).
> * Compare AWS Bedrock Guardrails against a custom application-level middleware.
> * Document how you plan to store user feedback (thumbs up/down) in DynamoDB and link it to the retrieved document chunks for future model fine-tuning or prompt engineering.

* **Bedrock Guardrails vs. Custom Middleware:** *[Evaluate pros and cons based on latency, control, and cost]*
* **Feedback Storage Schema:** *[Design a schema to map feedback to trace IDs so you can isolate why a user gave a thumbs down]*

---

## Next Steps for the Team
1. Review this guide.
2. Complete the background research homework blocks.
3. Choose the target stack (e.g., Langfuse for Tracing, Ragas for CI/CD metrics).
4. Implement telemetry decorators on the newly completed `chat` and `retrieve` endpoints.
