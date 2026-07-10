from pydantic_settings import BaseSettings, SettingsConfigDict

from rag_shared.config import get_shared_settings


class APISettings(BaseSettings):
    # Fetch default settings from shared-lib config
    _shared = get_shared_settings()

    qdrant_host: str = _shared.qdrant_host
    qdrant_api_key: str | None = _shared.qdrant_api_key
    qdrant_collection: str = _shared.qdrant_collection

    embedding_model: str = _shared.embedding_model
    chat_model: str = _shared.chat_model
    aws_region: str = _shared.aws_region

    # API specific configurations
    api_rate_limit_per_minute: int = 60
    allowed_cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


def get_api_settings() -> APISettings:
    return APISettings()
