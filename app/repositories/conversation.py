import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conversation


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation | None:
        return self.db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )

    def list_by_user(self, user_id: uuid.UUID) -> list[Conversation]:
        return list(
            self.db.scalars(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc())
            )
        )

    def create(self, user_id: uuid.UUID, title: str) -> Conversation:
        conversa = Conversation(user_id=user_id, title=title)
        self.db.add(conversa)
        self.db.flush()
        return conversa

    def delete(self, conversa: Conversation) -> None:
        self.db.delete(conversa)
