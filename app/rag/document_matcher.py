import logging
import unicodedata
import uuid

from app.llm import Modelo
from app.models import Document

logger = logging.getLogger(__name__)

PROMPT = """Documentos de um usuário, numerados:

{catalogo}

Pergunta: "{pergunta}"

A pergunta se refere a algum documento específico da lista?
Responda apenas com JSON: {{"indices": [n]}}
Lista vazia se for genérica ou não citar nenhum."""


def detectar(
    pergunta: str, documentos: list[Document], llm: Modelo | None = None
) -> list[uuid.UUID]:
    if not documentos:
        return []

    if alvos := _match_textual(pergunta, documentos):
        return alvos

    return _match_llm(pergunta, documentos, llm)


def _normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _match_textual(pergunta: str, documentos: list[Document]) -> list[uuid.UUID]:
    pergunta_norm = _normalizar(pergunta)
    return [
        doc.id
        for doc in documentos
        if any(
            _normalizar(i) in pergunta_norm for i in (doc.identifiers or []) if i
        )
    ]


def _match_llm(
    pergunta: str, documentos: list[Document], llm: Modelo | None
) -> list[uuid.UUID]:
    catalogo = "\n".join(
        f"{i}. [{doc.doc_type}] {doc.title} — "
        f"{', '.join(doc.identifiers or []) or 'sem identificadores'}"
        for i, doc in enumerate(documentos)
    )

    try:
        dados = (llm or Modelo()).completar_json(
            PROMPT.format(catalogo=catalogo, pergunta=pergunta)
        )
        indices = dados["indices"]
    except Exception:
        logger.warning("detecção por LLM falhou", exc_info=True)
        return []

    if not isinstance(indices, list):
        return []

    return [
        documentos[i].id
        for i in indices
        if isinstance(i, int) and 0 <= i < len(documentos)
    ]
