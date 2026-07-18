import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from langchain_aws import ChatBedrock, BedrockEmbeddings
from src.config import get_eval_settings

def calculate_generation_metrics(df: pd.DataFrame) -> dict:
    """
    Calculates generation metrics using ragas LLM-as-a-judge.
    
    Args:
        df: pandas DataFrame containing 'question', 'answer', 'contexts', 'ground_truth'
        
    Returns:
        dict containing the aggregated ragas metrics and the raw scores per row
    """
    settings = get_eval_settings()
    
    eval_llm = ChatBedrock(
        model_id=settings.eval_model,
        region_name=settings.aws_region,
        model_kwargs={"temperature": 0.0}
    )
    
    eval_embeddings = BedrockEmbeddings(
        model_id=settings.embedding_model,
        region_name=settings.aws_region,
    )
    
    # Convert pandas dataframe to HuggingFace Dataset required by ragas
    dataset = Dataset.from_pandas(df)
    
    # Initialize metrics
    metrics = [faithfulness, answer_relevancy]
    
    print("Evaluating generation with Ragas...")
    result = evaluate(
        dataset,
        metrics=metrics,
        llm=eval_llm,
        embeddings=eval_embeddings
    )
    
    return {
        "aggregated": result,
        "raw_scores": result.to_pandas()
    }
