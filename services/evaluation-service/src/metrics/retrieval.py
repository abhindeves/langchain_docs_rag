from ranx import Qrels, Run, evaluate

def calculate_retrieval_metrics(ground_truth_docs: dict[str, list[str]], retrieved_docs: dict[str, list[str]]):
    """
    Calculates deterministic retrieval metrics using ranx.
    
    Args:
        ground_truth_docs: dict of query_id -> list of relevant document IDs (e.g., {"q1": ["docA", "docB"]})
        retrieved_docs: dict of query_id -> list of retrieved document IDs in ranked order
    
    Returns:
        dict containing MRR, MAP, NDCG, Precision@K, Recall@K
    """
    
    # Format Qrels (Ground Truth) for ranx
    qrels_dict = {}
    for q_id, doc_ids in ground_truth_docs.items():
        qrels_dict[q_id] = {doc_id: 1 for doc_id in doc_ids}
    qrels = Qrels(qrels_dict)
    
    # Format Run (Retrieved Results) for ranx
    run_dict = {}
    for q_id, doc_ids in retrieved_docs.items():
        # Rank by position (higher score = better rank, so we give highest score to first item)
        run_dict[q_id] = {doc_id: len(doc_ids) - i for i, doc_id in enumerate(doc_ids)}
    run = Run(run_dict)
    
    # Calculate metrics
    metrics = ["mrr", "map", "ndcg", "precision@3", "recall@3", "precision@5", "recall@5"]
    results = evaluate(qrels, run, metrics)
    
    return results
