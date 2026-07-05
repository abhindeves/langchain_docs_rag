from rag_shared.config import SharedSettings, get_shared_settings


def test_shared_settings_defaults(monkeypatch):
    monkeypatch.delenv("QDRANT_HOST", raising=False)
    monkeypatch.delenv("QDRANT_CLUSTER_ENDPOINT", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)

    settings = SharedSettings()
    assert settings.qdrant_host == ""
    assert settings.embedding_model == "amazon.titan-embed-text-v2:0"


def test_shared_settings_env_override(monkeypatch):
    monkeypatch.setenv("QDRANT_HOST", "test-host")
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-model")

    settings = get_shared_settings()
    assert settings.qdrant_host == "test-host"
    assert settings.embedding_model == "custom-model"
