import uuid

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Conversation, Message, MessageRole
from app.rag import prompt
from app.repositories.chunk import ChunkEncontrado
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository
from app.services.retrieval_service import RetrievalService

TITULO_MAX = 60


class ConversationNotFound(Exception):
    pass


class ChatService:
    def __init__(
        self,
        db: Session,
        retrieval: RetrievalService | None = None,
        client: OpenAI | None = None,
    ):
        self.db = db
        self.conversas = ConversationRepository(db)
        self.mensagens = MessageRepository(db)
        self._retrieval = retrieval
        self._client = client

    @property
    def retrieval(self) -> RetrievalService:
        if self._retrieval is None:
            self._retrieval = RetrievalService(self.db)
        return self._retrieval

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    def criar_conversa(self, user_id: uuid.UUID, title: str | None) -> Conversation:
        conversa = self.conversas.create(user_id, title or "Nova conversa")
        self.db.commit()
        return conversa

    def listar_conversas(self, user_id: uuid.UUID) -> list[Conversation]:
        return self.conversas.list_by_user(user_id)

    def obter_conversa(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation:
        conversa = self.conversas.get(conversation_id, user_id)
        if conversa is None:
            raise ConversationNotFound("conversa não encontrada")
        return conversa

    def listar_mensagens(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[Message]:
        self.obter_conversa(conversation_id, user_id)
        return self.mensagens.list_by_conversation(conversation_id)

    def deletar_conversa(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        self.conversas.delete(self.obter_conversa(conversation_id, user_id))
        self.db.commit()

    def responder(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, pergunta: str
    ) -> Message:
        conversa = self.obter_conversa(conversation_id, user_id)

        self.mensagens.create(conversa.id, MessageRole.USER, pergunta)
        if conversa.title == "Nova conversa":
            conversa.title = pergunta[:TITULO_MAX]

        encontrados = self.retrieval.buscar(user_id, pergunta)

        if not encontrados:
            resposta = self.mensagens.create(
                conversa.id, MessageRole.ASSISTANT, prompt.SEM_CONTEXTO, sources=[]
            )
            self.db.commit()
            return resposta

        historico = self.mensagens.ultimas(
            conversa.id, settings.history_message_count
        )
        texto = self._gerar(pergunta, encontrados, historico[:-1])

        resposta = self.mensagens.create(
            conversa.id,
            MessageRole.ASSISTANT,
            texto,
            sources=[_fonte(e) for e in encontrados],
        )
        self.db.commit()
        return resposta

    def _gerar(
        self,
        pergunta: str,
        encontrados: list[ChunkEncontrado],
        historico: list[Message],
    ) -> str:
        resposta = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=prompt.montar_mensagens(pergunta, encontrados, historico),
        )
        return resposta.choices[0].message.content or ""


def _fonte(encontrado: ChunkEncontrado) -> dict:
    documento = encontrado.documento
    return {
        "document_id": str(documento.id),
        "document_title": documento.title or documento.filename,
        "page": encontrado.chunk.page,
        "score": round(encontrado.score, 4),
        "excerpt": encontrado.chunk.content[:300],
    }
