# api/config.py

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from .env
    """

    # =========================================================
    # GROQ
    # =========================================================
    GROQ_API_KEY: str = ""
    GROQ_INTENT_MODEL: str = "openai/gpt-oss-20b"
    GROQ_REWRITER_MODEL: str = "openai/gpt-oss-20b"
    GROQ_PLANNER_MODEL: str = "llama-3.3-70b-versatile"

    # =========================================================
    # QDRANT
    # =========================================================
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_NAME: str = "workout_embeddings"

    # =========================================================
    # AGENT CONFIG
    # =========================================================
    AGENT_THREAD_POOL_SIZE: int = 4
    REQUEST_TIMEOUT_SECONDS: int = 120

    # =========================================================
    # RETRIEVAL
    # =========================================================
    USE_HYBRID: bool = False

    # =========================================================
    # SEMANTIC CACHE (Redis)
    # =========================================================
    REDIS_URL: str = "electric-tulip-ultrafresh-50461.db.redis.io:13770"                                # empty => cache disabled
    SEMANTIC_CACHE_ENABLED: bool = True
    SEMANTIC_CACHE_INDEX_NAME: str = "chat_semcache"
    SEMANTIC_CACHE_DISTANCE_THRESHOLD: float = 0.1     # cosine distance; smaller = stricter match
    SEMANTIC_CACHE_TTL_SECONDS: int = 3600
    SEMANTIC_CACHE_EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"

    # =========================================================
    # CORS
    # =========================================================
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
        ]
    )

    # =========================================================
    # PYDANTIC SETTINGS CONFIG
    # =========================================================
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance
    """
    return Settings()


# Singleton settings object
settings = get_settings()
