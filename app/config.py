import os
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    class Settings(BaseSettings):
        APP_NAME: str = "Autonomous-MultiAgent-Pipeline"
        ENVIRONMENT: str = "development"
        LOG_LEVEL: str = "INFO"

        DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agentic_db"
        REDIS_URL: str = "redis://localhost:6379/0"

        OPENAI_API_KEY: Optional[str] = None
        LLM_MODEL: str = "gpt-4o-mini"
        EMBEDDING_MODEL: str = "text-embedding-3-small"
        EMBEDDING_DIMENSION: int = 1536

        TOP_K_SPARSE: int = 10
        TOP_K_DENSE: int = 10
        TOP_K_FINAL: int = 5
        RRF_K: int = 60
        RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    settings = Settings()

except ImportError:
    class FallbackSettings:
        APP_NAME: str = os.getenv("APP_NAME", "Autonomous-MultiAgent-Pipeline")
        ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

        DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/agentic_db")
        REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
        LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
        EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "1536"))

        TOP_K_SPARSE: int = int(os.getenv("TOP_K_SPARSE", "10"))
        TOP_K_DENSE: int = int(os.getenv("TOP_K_DENSE", "10"))
        TOP_K_FINAL: int = int(os.getenv("TOP_K_FINAL", "5"))
        RRF_K: int = int(os.getenv("RRF_K", "60"))
        RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

    settings = FallbackSettings()
