import enum
import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampCreated, TimestampUpdated, UUIDPrimaryKey


class DocumentStatus(enum.StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentType(enum.StrEnum):
    CONTRATO = "contrato"
    LEI = "lei"
    SUMULA = "sumula"
    JURISPRUDENCIA = "jurisprudencia"
    PARECER = "parecer"
    OUTRO = "outro"


class Document(Base, UUIDPrimaryKey, TimestampCreated, TimestampUpdated):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(500))
    storage_key: Mapped[str] = mapped_column(String(500))
    status: Mapped[DocumentStatus] = mapped_column(
        String(20), default=DocumentStatus.UPLOADED
    )

    title: Mapped[str | None] = mapped_column(String(500))
    doc_type: Mapped[DocumentType | None] = mapped_column(String(20))
    identifiers: Mapped[list[str] | None] = mapped_column(JSONB)

    page_count: Mapped[int | None]
    chunk_count: Mapped[int | None]
    error_message: Mapped[str | None] = mapped_column(Text)
