from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://docmind:docmind@localhost:5435/docmind"

    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1536

    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_top_k: int = 5
    similarity_threshold: float = 0.3
    history_message_count: int = 10

    max_upload_mb: int = 20
    stuck_processing_minutes: int = 15

    jwt_secret: str = "dev-secret-trocar-em-producao"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    google_client_id: str = ""

    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_access_key: str = "docmind"
    s3_secret_key: str = "docmind123"
    s3_bucket: str = "documents"
    presigned_url_minutes: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
