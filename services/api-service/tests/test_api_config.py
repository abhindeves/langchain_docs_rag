from api.config import APISettings, get_api_settings


def test_api_settings_defaults():
    """Verify that default settings are loaded correctly from shared settings and defaults."""
    settings = get_api_settings()
    assert settings.api_rate_limit_per_minute == 60
    assert settings.allowed_cors_origins == ["*"]
    assert settings.embedding_model == "amazon.titan-embed-text-v2:0"


def test_api_settings_env_overrides(monkeypatch):
    """Verify that environment variables successfully override configuration defaults."""
    monkeypatch.setenv("API_RATE_LIMIT_PER_MINUTE", "120")
    monkeypatch.setenv("ALLOWED_CORS_ORIGINS", '["http://localhost:3000", "https://example.com"]')
    monkeypatch.setenv("QDRANT_HOST", "http://qdrant.test")
    monkeypatch.setenv("QDRANT_API_KEY", "test-api-key")

    # Instantiate a new settings object to read the mocked environment
    settings = APISettings()
    assert settings.api_rate_limit_per_minute == 120
    assert settings.allowed_cors_origins == ["http://localhost:3000", "https://example.com"]
    assert settings.qdrant_host == "http://qdrant.test"
    assert settings.qdrant_api_key == "test-api-key"
