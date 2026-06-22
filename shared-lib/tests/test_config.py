from shared.config import get_shared_settings


def test_shared_settings_defaults():
    settings = get_shared_settings()
    assert settings.qdrant_host in (
        "localhost",
        "qdrant",
    )  # Allow either depending on local environment
    assert settings.qdrant_port == 6333
    assert settings.embedding_model == "amazon.titan-embed-text-v2:0"


def test_shared_settings_env_override(monkeypatch):
    monkeypatch.setenv("QDRANT_HOST", "test-host")
    monkeypatch.setenv("QDRANT_PORT", "1234")
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-model")

    settings = get_shared_settings()
    assert settings.qdrant_host == "test-host"
    assert settings.qdrant_port == 1234
    assert settings.embedding_model == "custom-model"
