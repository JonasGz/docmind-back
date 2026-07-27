import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import (
    Base,
    TimestampCreated,
    TimestampUpdated,
    UUIDPrimaryKey,
    valores_do_enum,
)


class DocumentStatus(enum.StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentType(enum.StrEnum):
    NORMA = "norma"
    JURISPRUDENCIA = "jurisprudencia"
    SUMULA = "sumula"
    CONTRATO = "contrato"
    PARECER = "parecer"
    PETICAO = "peticao"
    COMUNICACAO = "comunicacao"
    EDITAL = "edital"
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
        Enum(
            DocumentStatus,
            native_enum=False,
            length=20,
            values_callable=valores_do_enum,
        ),
        default=DocumentStatus.UPLOADED,
    )

    title: Mapped[str | None] = mapped_column(String(500))
    doc_type: Mapped[DocumentType | None] = mapped_column(
        Enum(
            DocumentType,
            native_enum=False,
            length=20,
            values_callable=valores_do_enum,
        )
    )
    raw_doc_type: Mapped[str | None] = mapped_column(String(100))
    identifiers: Mapped[list[str] | None] = mapped_column(JSONB)

    page_count: Mapped[int | None]
    chunk_count: Mapped[int | None]
    error_message: Mapped[str | None] = mapped_column(Text)
