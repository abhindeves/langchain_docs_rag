from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SharedSettings(BaseSettings):
    qdrant_host: str = Field(
        default="",
        validation_alias=AliasChoices("qdrant_host", "qdrant_cluster_endpoint"),
    )
    qdrant_api_key: str | None = None

    # Common RAG settings
    embedding_model: str = "amazon.titan-embed-text-v2:0"
    chat_model: str = "anthropic.claude-3-haiku-20240307-v1:0"
    aws_region: str = "ap-south-1"
    s3_bucket: str = "rag-document-store"
    sqs_queue_url: str = "rag-ingestion-queue"
    qdrant_collection: str = "documents"

    # Reads environment variables or local .env automatically
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_shared_settings() -> SharedSettings:
    return SharedSettings()
