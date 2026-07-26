import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentStatus


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Document | None:
        return self.db.scalar(
            select(Document).where(
                Document.id == document_id, Document.user_id == user_id
            )
        )

    def list_by_user(self, user_id: uuid.UUID) -> list[Document]:
        return list(
            self.db.scalars(
                select(Document)
                .where(Document.user_id == user_id)
                .order_by(Document.created_at.desc())
            )
        )

    def list_indexed(self, user_id: uuid.UUID) -> list[Document]:
        return list(
            self.db.scalars(
                select(Document).where(
                    Document.user_id == user_id,
                    Document.status == DocumentStatus.INDEXED,
                )
            )
        )

    def create(
        self, user_id: uuid.UUID, filename: str, storage_key: str
    ) -> Document:
        documento = Document(
            user_id=user_id,
            filename=filename,
            storage_key=storage_key,
            status=DocumentStatus.PROCESSING,
        )
        self.db.add(documento)
        self.db.flush()
        return documento

    def delete(self, documento: Document) -> None:
        self.db.delete(documento)

    def marcar_travados_como_falha(self, user_id: uuid.UUID) -> None:
        limite = datetime.now(UTC) - timedelta(
            minutes=settings.stuck_processing_minutes
        )
        travados = self.db.scalars(
            select(Document).where(
                Document.user_id == user_id,
                Document.status == DocumentStatus.PROCESSING,
                Document.updated_at < limite,
            )
        )
        for documento in travados:
            documento.status = DocumentStatus.FAILED
            documento.error_message = "processamento interrompido"
