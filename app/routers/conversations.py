import uuid

from fastapi import APIRouter, HTTPException, status

from app.dependencies import CurrentUser, DbSession
from app.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
)
from app.services.chat_service import ChatService, ConversationNotFound

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(
    payload: ConversationCreate, user: CurrentUser, db: DbSession
) -> ConversationResponse:
    conversa = ChatService(db).criar_conversa(user.id, payload.title)
    return ConversationResponse.model_validate(conversa)


@router.get("")
def listar(user: CurrentUser, db: DbSession) -> ConversationListResponse:
    conversas = ChatService(db).listar_conversas(user.id)
    return ConversationListResponse(
        items=[ConversationResponse.model_validate(c) for c in conversas]
    )


@router.get("/{conversation_id}/messages")
def listar_mensagens(
    conversation_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> MessageListResponse:
    try:
        mensagens = ChatService(db).listar_mensagens(conversation_id, user.id)
    except ConversationNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return MessageListResponse(
        items=[MessageResponse.model_validate(m) for m in mensagens]
    )


@router.post("/{conversation_id}/messages")
def enviar_mensagem(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    user: CurrentUser,
    db: DbSession,
) -> MessageResponse:
    if not payload.content.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "pergunta vazia")

    try:
        resposta = ChatService(db).responder(
            conversation_id, user.id, payload.content
        )
    except ConversationNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return MessageResponse.model_validate(resposta)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(conversation_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    try:
        ChatService(db).deletar_conversa(conversation_id, user.id)
    except ConversationNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
