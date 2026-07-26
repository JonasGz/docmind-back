import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import MessageRole


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]


class MessageCreate(BaseModel):
    content: str


class Source(BaseModel):
    document_id: uuid.UUID
    document_title: str
    page: int
    score: float
    excerpt: str


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    sources: list[Source] | None
    created_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
