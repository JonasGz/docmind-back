import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import DocumentStatus, DocumentType


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    status: DocumentStatus
    title: str | None
    doc_type: DocumentType | None
    raw_doc_type: str | None
    identifiers: list[str] | None
    page_count: int | None
    chunk_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]


class DownloadUrlResponse(BaseModel):
    url: str
    expires_in_seconds: int
