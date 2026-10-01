"""Application settings loaded from the environment and an optional `.env` file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "test", "production"] = "local"
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_stub_on_unavailable: bool = True
    ollama_health_timeout: float = 3.0
    ollama_generate_timeout: float = 120.0
    ollama_num_ctx: int = Field(4096, ge=512)
    ollama_temperature: float = Field(0.0, ge=0.0, le=2.0)

    # Embedding backend: sentence-transformers | ollama | hash_stub.
    # The default MiniLM runs on CPU and works offline once downloaded, so
    # ingest does not need Ollama.
    embedding_backend: str = "sentence-transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"

    chunk_size: int = Field(800, ge=50)
    chunk_overlap: int = Field(120, ge=0)
    summarize_top_k: int = Field(8, ge=1, le=20)
    verify_top_k: int = Field(5, ge=1, le=20)

    max_upload_mb: int = Field(20, ge=1)

    data_dir: Path = Path("./data")
    chroma_path: Path = Path("./data/chroma")
    upload_dir: Path = Path("./data/uploads")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
