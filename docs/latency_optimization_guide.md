# Production RAG Latency Optimization Strategy & Study Guide

This document outlines the roadmap for transitioning our Retrieval-Augmented Generation (RAG) platform from its current local development state to a low-latency, production-ready system.

It is designed as a **collaborative design document**. Some sections are complete, while others contain **Study & Homework Assignments** to guide you through the necessary engineering trade-offs. You are encouraged to research these topics and enrich this document with your findings.

---

## 1. Profiled Baseline (Current Local Monorepo)

Based on a test query running locally in our development environment:
* **Query:** `"explain langgraph routing"`
* **Embeddings:** Bedrock Titan (`ap-south-1`)
* **Vector DB:** Qdrant Cloud (`eu-central-1` / Frankfurt)
* **Reranker:** Bedrock Agent Runtime Rerank (`ap-northeast-1` / Tokyo)
* **LLM:** Claude 3 Haiku via Bedrock (`ap-south-1`)

| Stage | Duration | Primary Bottleneck |
| :--- | :---: | :--- |
| **1. Query Embedding** | `0.289s` | Initial API handshake with AWS Bedrock. |
| **2. Qdrant Retrieval** | `0.884s` | Cross-region network call (Local -> Frankfurt). |
| **3. Bedrock Reranking** | `1.505s` | Cross-region network call (Local -> Tokyo) + API latency. |
| **4. LLM Generation** | `2.947s` | Blocking token generation (TTFT is coupled to the total response time). |
| **Total Cumulative Time** | **`5.625s`** | **Blocking, high-latency user experience.** |

---

## 2. Infrastructure & Network Optimization (Target: <100ms total overhead)

### The Production Goal
Co-locate all services within the same AWS Region (e.g., `us-east-1` or `ap-south-1`) and use **AWS PrivateLink / VPC Endpoints** for secure, low-latency, in-network connectivity.

```
[ FastAPI App (VPC Private Subnet) ]
       │
       ├──(PrivateLink)──> [ Amazon Bedrock Endpoint (Same Region) ]
       │
       └──(VPC Peering)──> [ Qdrant Cloud (Same Region / Availability Zone) ]
```

### 📝 Background Study & Document Enrichment
> [!IMPORTANT]
> **Your Task:** Research AWS PrivateLink and VPC Peering latencies compared to public routing.
> * Fill in the latency differences you find in the placeholder table below.
> * Document how to configure `boto3` to use a custom VPC endpoint URL for Bedrock.

```python
# HOMEWORK: Fill in the code snippet to configure the Bedrock Client with a custom VPC Endpoint URL
import boto3
from botocore.config import Config

client = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-east-1",
    # endpoint_url="YOUR_VPC_ENDPOINT_URL_HERE", # Explain how to retrieve this from Pulumi/Terraform outputs
)
```

| Route Type | Estimated Latency | Cost/Security Implications |
| :--- | :---: | :--- |
| Public Internet Routing | *[Your findings here]* | *[Your findings here]* |
| AWS VPC Endpoint (PrivateLink) | *[Your findings here]* | *[Your findings here]* |

---

## 3. Vector DB & Retrieval Optimization (Target: <50ms)

### The Production Goal
Configure Qdrant for optimal indexing, payload caching, and vector quantization to accelerate search over large datasets.

### 📝 Background Study & Document Enrichment
> [!IMPORTANT]
> **Your Task:** Read Qdrant’s indexing documentation regarding **HNSW (Hierarchical Navigable Small World)** parameters and **Scalar Quantization**.
> 1. Study the trade-off between search speed, memory footprint, and recall accuracy when enabling `scalar_quantization`.
> 2. Document the correct payload index types for the filters we use (e.g., keyword index vs. integer index).
> 3. Complete the configuration payload below to optimize the collection setup.

```json
// HOMEWORK: Complete the Qdrant Collection parameters for production optimization
{
  "vectors": {
    "dense_vector": {
      "size": 1024,
      "distance": "Cosine"
    }
  },
  "hnsw_config": {
    // "m": 16, // Research: What does 'm' do to search speed and indexing time?
    // "ef_construct": 100 // Research: How does this impact indexing?
  },
  "optimizers_config": {
    // Fill in recommended optimizers configurations
  },
  "quantization_config": {
    // Research and define a Scalar Quantization (int8) configuration here
  }
}
```

---

## 4. Reranking Strategy: API vs. Sidecar (Target: <100ms)

### The Production Goal
Replace the remote API-based reranker (which adds 1.5s latency) with a local sidecar model or a highly optimized CPU/GPU-based inference service.

```
Option A: FastAPI ──(HTTPS)──> Bedrock Agent Rerank (Tokyo) [Latency: 1500ms]
Option B: FastAPI ──(Localhost IPC)──> ONNX Rerank Container [Latency: 50ms]
```

### 📝 Background Study & Document Enrichment
> [!IMPORTANT]
> **Your Task:** Research deploying a cross-encoder model (e.g., `BAAI/bge-reranker-base` or `ms-marco-MiniLM-L-6-v2`) using **ONNX Runtime** or **Hugging Face TEI (Text Embeddings Inference)**.
> * Compare Option A (Managed Bedrock Reranker) vs. Option B (Local ONNX/TEI sidecar container).
> * Fill out the comparison matrix below based on your research.

| Metric | Option A: Bedrock Reranker | Option B: Local Sidecar (TEI/ONNX) |
| :--- | :---: | :---: |
| **Latency** | ~1.5s | *[Your findings]* |
| **Operational Overhead** | Serverless / zero config | *[Your findings]* |
| **Cost Scale** | Per-request billing | Container hosting costs (CPU/GPU) |
| **Hardware Requirements** | None | *[Your findings]* |

---

## 5. Streaming & Prompt Caching (Target TTFT: <250ms)

### The Production Goal
Deliver generated text to the client character-by-character using HTTP Streaming. Enable Bedrock prompt caching to speed up context analysis.

### 📝 Background Study & Document Enrichment
> [!IMPORTANT]
> **Your Task:** Study the Bedrock Converse Stream API and FastAPI’s `StreamingResponse`.
> 1. Write a prototype for an asynchronous stream handler in Python.
> 2. Investigate Bedrock Prompt Caching rules (minimum token requirements, caching duration, billing structures) and fill in the checklist below.

```python
# HOMEWORK: Complete this FastAPI route handler draft to stream tokens from Bedrock Converse Stream
from fastapi.responses import StreamingResponse

async def token_generator(system, messages):
    # Hint: Use self.client.converse_stream(...)
    # Loop over the stream events and yield text chunks
    pass

@router.post("/chat/stream")
async def chat_stream(request: Request, payload: ChatRequest):
    # Invoke generator and wrap in StreamingResponse
    # return StreamingResponse(token_generator(...), media_type="text/event-stream")
    pass
```

* [ ] **Prompt Caching Minimum Tokens Requirement:** *[Fill in minimum tokens required to trigger cache]*
* [ ] **Cache TTL (Time-To-Live):** *[Fill in how long the Bedrock prompt cache stays warm]*
* [ ] **Pricing Delta:** *[Fill in the cost savings of cached input tokens vs. uncached input tokens]*

---

## 6. Semantic Cache Layer (Target: <30ms)

### The Production Goal
Deploy a fast cache layer using Redis or Qdrant itself to intercept queries before running the RAG pipeline.

```
User Query ──> [ Embed query ]
                     │
              [ Search Cache ] ──(Similarity > 0.96)──> [ Return Cached Answer ] (Instant <30ms)
                     │
              (Similarity < 0.96)
                     │
                     └──> [ Execute full Qdrant -> Rerank -> LLM pipeline ]
```

### 📝 Background Study & Document Enrichment
> [!IMPORTANT]
> **Your Task:** Research **Semantic Caching** libraries (e.g., `GPTCache` or writing custom Redis-based vector search).
> * What threshold of cosine similarity is safe to return a cached answer without risking hallucination or out-of-context replies?
> * How do you handle cache invalidation when underlying documents are updated in Qdrant?

---

## Next Steps for the Team
1. Review the proposed architecture.
2. Complete the background study blocks and check in the enriched version of this document.
3. Schedule Phase 3 (Latency Optimization & Evaluations) sprint planning.
