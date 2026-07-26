import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DocumentChunk
from app.rag.splitter import ChunkExtraido


class ChunkRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_many(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        chunks: list[ChunkExtraido],
        embeddings: list[list[float]],
        embedding_model: str,
    ) -> int:
        registros = [
            DocumentChunk(
                document_id=document_id,
                user_id=user_id,
                page=chunk.pagina,
                chunk_index=chunk.indice,
                content=chunk.conteudo,
                embedding=embedding,
                embedding_model=embedding_model,
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        self.db.add_all(registros)
        self.db.flush()
        return len(registros)

    def contar_por_documento(
        self, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.user_id == user_id,
            )
        ) or 0
