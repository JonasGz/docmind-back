from unittest.mock import MagicMock, patch

from app.models import MessageRole
from app.rag import prompt
from app.repositories.message import MessageRepository
from app.services.chat_service import ChatService
from app.services.retrieval_service import RetrievalService


def _chat(db, embeddings_falsos, resposta="Resposta do modelo."):
    llm = MagicMock()
    llm.chat.completions.create.return_value.choices[0].message.content = resposta
    return ChatService(
        db,
        retrieval=RetrievalService(db, embeddings=embeddings_falsos),
        client=llm,
    ), llm


def test_role_lido_do_banco_e_enum(db, usuario_a, embeddings_falsos):
    servico, _ = _chat(db, embeddings_falsos)
    conversa = servico.criar_conversa(usuario_a.id, None)
    MessageRepository(db).create(conversa.id, MessageRole.USER, "olá")
    db.commit()
    db.expire_all()

    mensagens = MessageRepository(db).list_by_conversation(conversa.id)

    assert isinstance(mensagens[0].role, MessageRole)
    assert mensagens[0].role.value == "user"


def test_segunda_pergunta_monta_prompt_com_historico(
    db, usuario_a, embeddings_falsos
):
    servico, llm = _chat(db, embeddings_falsos)
    conversa = servico.criar_conversa(usuario_a.id, None)

    with patch.object(
        servico.retrieval, "buscar", return_value=[]
    ):
        servico.responder(conversa.id, usuario_a.id, "primeira pergunta")

    mensagens = MessageRepository(db).list_by_conversation(conversa.id)
    historico = prompt.montar_mensagens("segunda pergunta", [], mensagens)

    assert historico[0]["role"] == "system"
    assert [m["role"] for m in historico[1:3]] == ["user", "assistant"]
    assert historico[-1]["content"].endswith("segunda pergunta")


def test_sem_contexto_relevante_nao_chama_a_llm(db, usuario_a, embeddings_falsos):
    servico, llm = _chat(db, embeddings_falsos)
    conversa = servico.criar_conversa(usuario_a.id, None)

    with patch.object(servico.retrieval, "buscar", return_value=[]):
        resposta = servico.responder(conversa.id, usuario_a.id, "pergunta qualquer")

    assert resposta.content == prompt.SEM_CONTEXTO
    assert resposta.sources == []
    assert not llm.chat.completions.create.called


def test_titulo_vem_da_primeira_pergunta(db, usuario_a, embeddings_falsos):
    servico, _ = _chat(db, embeddings_falsos)
    conversa = servico.criar_conversa(usuario_a.id, None)

    with patch.object(servico.retrieval, "buscar", return_value=[]):
        servico.responder(conversa.id, usuario_a.id, "qual a multa de rescisão?")

    db.refresh(conversa)
    assert conversa.title == "qual a multa de rescisão?"
