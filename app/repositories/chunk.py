import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.rag.splitter import ChunkExtraido


@dataclass
class ChunkEncontrado:
    chunk: DocumentChunk
    documento: Document
    score: float


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

    def search(
        self,
        user_id: uuid.UUID,
        embedding: list[float],
        k: int,
        threshold: float,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[ChunkEncontrado]:
        distancia = DocumentChunk.embedding.cosine_distance(embedding)

        stmt = (
            select(DocumentChunk, Document, distancia.label("distancia"))
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.user_id == user_id)
        )

        if document_ids:
            stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))

        stmt = stmt.order_by(distancia).limit(k)

        return [
            ChunkEncontrado(chunk=chunk, documento=documento, score=1 - distancia)
            for chunk, documento, distancia in self.db.execute(stmt)
            if 1 - distancia >= threshold
        ]

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
