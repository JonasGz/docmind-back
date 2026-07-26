import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.rag import document_matcher
from app.repositories.chunk import ChunkEncontrado, ChunkRepository
from app.repositories.document import DocumentRepository
from app.services.embedding_service import EmbeddingService


class RetrievalService:
    def __init__(self, db: Session, embeddings: EmbeddingService | None = None):
        self.db = db
        self.chunks = ChunkRepository(db)
        self.documentos = DocumentRepository(db)
        self._embeddings = embeddings

    @property
    def embeddings(self) -> EmbeddingService:
        if self._embeddings is None:
            self._embeddings = EmbeddingService()
        return self._embeddings

    def buscar(self, user_id: uuid.UUID, pergunta: str) -> list[ChunkEncontrado]:
        indexados = self.documentos.list_indexed(user_id)
        if not indexados:
            return []

        alvos = document_matcher.detectar(pergunta, indexados)

        return self.chunks.search(
            user_id=user_id,
            embedding=self.embeddings.gerar_um(pergunta),
            k=settings.retrieval_top_k,
            threshold=settings.similarity_threshold,
            document_ids=alvos or None,
        )
