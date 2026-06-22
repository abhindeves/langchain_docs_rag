from pydantic_settings import BaseSettings, SettingsConfigDict


class SharedSettings(BaseSettings):
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None

    # Common RAG settings
    embedding_model: str = "amazon.titan-embed-text-v2:0"
    aws_region: str = "ap-south-1"
    aws_bearer_token_bedrock: str | None = None

    # Reads environment variables or local .env automatically
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_shared_settings() -> SharedSettings:
    return SharedSettings()
