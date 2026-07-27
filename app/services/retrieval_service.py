import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.llm import Modelo
from app.rag import document_matcher
from app.repositories.chunk import ChunkEncontrado, ChunkRepository
from app.repositories.document import DocumentRepository


class RetrievalService:
    def __init__(self, db: Session, llm: Modelo | None = None):
        self.db = db
        self.chunks = ChunkRepository(db)
        self.documentos = DocumentRepository(db)
        self._llm = llm

    @property
    def llm(self) -> Modelo:
        if self._llm is None:
            self._llm = Modelo()
        return self._llm

    def buscar(self, user_id: uuid.UUID, pergunta: str) -> list[ChunkEncontrado]:
        indexados = self.documentos.list_indexed(user_id)
        if not indexados:
            return []

        alvos = document_matcher.detectar(pergunta, indexados, llm=self.llm)

        return self.chunks.search(
            user_id=user_id,
            embedding=self.llm.embutir_um(pergunta),
            k=settings.retrieval_top_k,
            threshold=settings.similarity_threshold,
            document_ids=alvos or None,
        )
