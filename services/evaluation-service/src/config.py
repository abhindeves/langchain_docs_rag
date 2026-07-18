import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class EvalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Models for Generation & Critic (Evaluation)
    eval_model: str = os.environ.get("EVAL_MODEL", "gemini-3.1-flash-lite")
    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "models/gemini-embedding-2")
    aws_region: str = os.environ.get("AWS_REGION", "ap-south-1")
    gemini_api_key: str = ""

    # Dataset Generation Config
    s3_bucket: str = os.environ.get("S3_BUCKET", "rag-document-store-57d6fd4")
    s3_prefix: str = os.environ.get("S3_EVAL_PREFIX", "raw/pages/")  # Prefix to pull subset

    # Ragas parameters
    testset_size: int = int(os.environ.get("TESTSET_SIZE", "5"))

    # Paths
    dataset_path: str = os.environ.get("DATASET_PATH", "data/golden_dataset.csv")


def get_eval_settings() -> EvalSettings:
    return EvalSettings()
