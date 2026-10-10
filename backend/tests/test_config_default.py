from app.core.config import Settings


def test_default_model_is_bggpt_v1_with_qwen_documented_fallback(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.ollama_model == "s_emanuilov/BgGPT-v1.0:9b"


def test_fallback_model_can_be_selected_via_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
    assert Settings(_env_file=None).ollama_model == "qwen2.5:7b"
