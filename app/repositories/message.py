import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Message, MessageRole


class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        return list(
            self.db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
        )

    def ultimas(self, conversation_id: uuid.UUID, limite: int) -> list[Message]:
        recentes = list(
            self.db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(limite)
            )
        )
        return list(reversed(recentes))

    def create(
        self,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        sources: list[dict] | None = None,
    ) -> Message:
        mensagem = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources,
        )
        self.db.add(mensagem)
        self.db.flush()
        return mensagem
