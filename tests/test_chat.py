import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.models import MessageRole
from app.rag import prompt
from app.repositories.chunk import ChunkEncontrado
from app.repositories.message import MessageRepository
from app.services.chat_service import ChatService
from app.services.retrieval_service import RetrievalService


def _chat(db, llm_falso):
    servico = ChatService(
        db,
        retrieval=RetrievalService(db, llm=llm_falso),
        llm=llm_falso,
    )
    return servico, llm_falso


def test_role_lido_do_banco_e_enum(db, usuario_a, llm_falso):
    servico, _ = _chat(db, llm_falso)
    conversa = servico.criar_conversa(usuario_a.id, None)
    MessageRepository(db).create(conversa.id, MessageRole.USER, "olá")
    db.commit()
    db.expire_all()

    mensagens = MessageRepository(db).list_by_conversation(conversa.id)

    assert isinstance(mensagens[0].role, MessageRole)
    assert mensagens[0].role.value == "user"


def test_segunda_pergunta_monta_prompt_com_historico(
    db, usuario_a, llm_falso
):
    servico, llm = _chat(db, llm_falso)
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


def test_sem_contexto_relevante_nao_chama_a_llm(db, usuario_a, llm_falso):
    servico, llm = _chat(db, llm_falso)
    conversa = servico.criar_conversa(usuario_a.id, None)

    with patch.object(servico.retrieval, "buscar", return_value=[]):
        resposta = servico.responder(conversa.id, usuario_a.id, "pergunta qualquer")

    assert resposta.content == prompt.SEM_CONTEXTO
    assert resposta.sources == []
    assert not llm.completar_chamado


def _encontrado(documento, page: int, content: str, score: float):
    chunk = SimpleNamespace(page=page, content=content)
    return ChunkEncontrado(chunk=chunk, documento=documento, score=score)


def _documento(nome: str = "Contrato de Locação"):
    return SimpleNamespace(id=uuid.uuid4(), title=nome, filename=f"{nome}.pdf",
                           identifiers=None)


def test_resposta_sem_etiqueta_nao_traz_fontes(db, usuario_a, llm_falso):
    documento = _documento()
    encontrados = [
        _encontrado(documento, 4, "trecho irrelevante", 0.55),
        _encontrado(documento, 9, "outro trecho irrelevante", 0.52),
    ]
    llm_falso.resposta = "Não encontrei informação sobre isso nos documentos."
    servico, _ = _chat(db, llm_falso)
    conversa = servico.criar_conversa(usuario_a.id, None)

    with patch.object(servico.retrieval, "buscar", return_value=encontrados):
        resposta = servico.responder(conversa.id, usuario_a.id, "pergunta sem resposta")

    assert resposta.sources == []


def test_fontes_sao_apenas_as_citadas_e_uma_por_pagina(db, usuario_a, llm_falso):
    documento = _documento()
    encontrados = [
        _encontrado(documento, 4, "prazo de 36 meses", 0.91),
        _encontrado(documento, 6, "rescisão antecipada", 0.88),
        _encontrado(documento, 6, "multa de três aluguéis", 0.72),
        _encontrado(documento, 20, "trecho não citado", 0.51),
    ]
    llm_falso.resposta = (
        "O prazo é de 36 meses (Contrato de Locação, p.4) [1]. "
        "A rescisão exige multa (Contrato de Locação, p.6) [2][3]."
    )
    servico, _ = _chat(db, llm_falso)
    conversa = servico.criar_conversa(usuario_a.id, None)

    with patch.object(servico.retrieval, "buscar", return_value=encontrados):
        resposta = servico.responder(conversa.id, usuario_a.id, "prazo e rescisão?")

    assert [(f["page"], f["score"]) for f in resposta.sources] == [(4, 0.91), (6, 0.88)]
    assert resposta.content == (
        "O prazo é de 36 meses (Contrato de Locação, p.4). "
        "A rescisão exige multa (Contrato de Locação, p.6)."
    )


def test_etiqueta_inexistente_e_ignorada(db, usuario_a, llm_falso):
    documento = _documento()
    encontrados = [_encontrado(documento, 4, "único trecho", 0.91)]
    llm_falso.resposta = "Afirmação com etiqueta inventada [7]."
    servico, _ = _chat(db, llm_falso)
    conversa = servico.criar_conversa(usuario_a.id, None)

    with patch.object(servico.retrieval, "buscar", return_value=encontrados):
        resposta = servico.responder(conversa.id, usuario_a.id, "pergunta")

    assert resposta.sources == []
    assert resposta.content == "Afirmação com etiqueta inventada."


def test_contexto_numera_trechos_para_a_llm():
    documento = _documento()
    contexto = prompt.montar_contexto(
        [
            _encontrado(documento, 4, "prazo de 36 meses", 0.91),
            _encontrado(documento, 6, "rescisão antecipada", 0.88),
        ]
    )

    assert "[1] (p.4) prazo de 36 meses" in contexto
    assert "[2] (p.6) rescisão antecipada" in contexto


def test_titulo_vem_da_primeira_pergunta(db, usuario_a, llm_falso):
    servico, _ = _chat(db, llm_falso)
    conversa = servico.criar_conversa(usuario_a.id, None)

    with patch.object(servico.retrieval, "buscar", return_value=[]):
        servico.responder(conversa.id, usuario_a.id, "qual a multa de rescisão?")

    db.refresh(conversa)
    assert conversa.title == "qual a multa de rescisão?"
