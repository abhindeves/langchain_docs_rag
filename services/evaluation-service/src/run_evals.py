import asyncio
import time
import pandas as pd
from langfuse import Langfuse
import httpx
from src.config import get_eval_settings
from src.metrics.retrieval import calculate_retrieval_metrics
from src.metrics.generation import calculate_generation_metrics

# To evaluate against the local API, ensure it's running on port 8000
API_URL = "http://localhost:8000/api/v1/chat"

async def evaluate_end_to_end():
    settings = get_eval_settings()
    langfuse = Langfuse()
    
    print(f"Loading dataset from {settings.dataset_path}")
    try:
        df = pd.read_csv(settings.dataset_path)
    except FileNotFoundError:
        print(f"Dataset not found at {settings.dataset_path}. Please run generate_testset.py first.")
        return
        
    print(f"Loaded {len(df)} evaluation queries.")
    
    # Store results
    retrieved_docs_map = {}
    ground_truth_map = {}
    generation_results = []
    
    # Generate Langfuse Session ID for this eval run
    session_id = f"eval-run-{int(time.time())}"
    print(f"Starting evaluation run (Session: {session_id})...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, row in df.iterrows():
            question = row["question"]
            ground_truth = row["ground_truth"]
            # ragas testset generator stores source docs/nodes in 'source_nodes'
            ground_truth_sources = eval(row.get("source_nodes", "[]")) 
            
            print(f"[{idx+1}/{len(df)}] Evaluating: {question}")
            
            # Start timer for overall latency and TTFT
            start_time = time.time()
            
            try:
                # We hit the chat endpoint. If streaming was enabled, we'd measure TTFT here.
                # For non-streaming, TTFT == Overall Latency.
                response = await client.post(API_URL, json={"query_text": question, "top_k": 5})
                response.raise_for_status()
                
                overall_latency = time.time() - start_time
                ttft = overall_latency # Placeholder for TTFT in non-streaming mode
                
                data = response.json()
                generated_answer = data["response"]
                sources = data["sources"]
                
                # Log to Langfuse
                trace = langfuse.trace(
                    name="e2e-eval-query",
                    session_id=session_id,
                    input=question,
                    output=generated_answer,
                    metadata={
                        "overall_latency": overall_latency,
                        "ttft": ttft,
                        "model": settings.eval_model
                    }
                )
                
                # Save for retrieval metrics
                q_id = f"q_{idx}"
                retrieved_ids = [doc.get("id") or str(doc.get("metadata", {}).get("filename")) for doc in sources]
                gt_ids = [node.get("filename") for node in ground_truth_sources if node.get("filename")]
                
                retrieved_docs_map[q_id] = retrieved_ids
                ground_truth_map[q_id] = gt_ids
                
                # Save for generation metrics
                generation_results.append({
                    "question": question,
                    "answer": generated_answer,
                    "contexts": [doc["text"] for doc in sources],
                    "ground_truth": ground_truth
                })
                
            except Exception as e:
                print(f"Error evaluating query: {e}")
                
    # 1. Compute Deterministic Retrieval Metrics
    if retrieved_docs_map and ground_truth_map:
        print("\n--- Retrieval Metrics (ranx) ---")
        retrieval_scores = calculate_retrieval_metrics(ground_truth_map, retrieved_docs_map)
        print(retrieval_scores)
    
    # 2. Compute LLM Generation Metrics
    if generation_results:
        print("\n--- Generation Metrics (ragas) ---")
        gen_df = pd.DataFrame(generation_results)
        gen_scores = calculate_generation_metrics(gen_df)
        print(gen_scores["aggregated"])
        
        # Save detailed results
        gen_scores["raw_scores"].to_csv("data/eval_results.csv", index=False)
        print("Detailed results saved to data/eval_results.csv")
        
    langfuse.flush()
    print("Done. Check your Langfuse dashboard for detailed trace latency and metrics.")

if __name__ == "__main__":
    asyncio.run(evaluate_end_to_end())
