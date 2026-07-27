from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-secret-inseguro-trocar-em-producao-com-openssl-rand"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "production"] = "development"

    database_url: str = "postgresql+psycopg://docmind:docmind@localhost:5435/docmind"

    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1536

    chunk_size: int = 1000
    chunk_overlap: int = 400
    retrieval_top_k: int = 5
    similarity_threshold: float = 0.50
    history_message_count: int = 10

    max_upload_mb: int = 20
    stuck_processing_minutes: int = 15

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    google_client_id: str = ""

    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_access_key: str = "docmind"
    s3_secret_key: str = "docmind123"
    s3_bucket: str = "docmind-storage"
    presigned_url_minutes: int = 10

    @model_validator(mode="after")
    def exigir_segredos_em_producao(self) -> Self:
        # .env com "JWT_SECRET=" sobrescreve o default por vazio
        if not self.jwt_secret:
            self.jwt_secret = DEV_JWT_SECRET

        if self.environment != "production":
            return self

        faltando = [
            nome
            for nome, valor in [
                ("JWT_SECRET", self.jwt_secret != DEV_JWT_SECRET),
                ("GOOGLE_CLIENT_ID", bool(self.google_client_id)),
                ("OPENAI_API_KEY", bool(self.openai_api_key)),
            ]
            if not valor
        ]
        if faltando:
            raise ValueError(f"variáveis obrigatórias em produção: {', '.join(faltando)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
