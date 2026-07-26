import json
import logging
import unicodedata
import uuid

from openai import OpenAI

from app.config import settings
from app.models import Document

logger = logging.getLogger(__name__)

PROMPT = """Documentos de um usuário, numerados:

{catalogo}

Pergunta: "{pergunta}"

A pergunta se refere a algum documento específico da lista?
Responda apenas com JSON: {{"indices": [n]}}
Lista vazia se for genérica ou não citar nenhum."""


def detectar(
    pergunta: str, documentos: list[Document], client: OpenAI | None = None
) -> list[uuid.UUID]:
    if not documentos:
        return []

    if alvos := _match_textual(pergunta, documentos):
        return alvos

    if not _parece_citar_documento(pergunta):
        return []

    return _match_llm(pergunta, documentos, client)


def _parece_citar_documento(pergunta: str) -> bool:
    palavras = pergunta.split()[1:]
    return any(
        p[0].isupper() or any(c.isdigit() for c in p) for p in palavras if p
    )


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
    pergunta: str, documentos: list[Document], client: OpenAI | None
) -> list[uuid.UUID]:
    catalogo = "\n".join(
        f"{i}. [{doc.doc_type}] {doc.title} — "
        f"{', '.join(doc.identifiers or []) or 'sem identificadores'}"
        for i, doc in enumerate(documentos)
    )

    try:
        cliente = client or OpenAI(api_key=settings.openai_api_key)
        resposta = cliente.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "user",
                    "content": PROMPT.format(catalogo=catalogo, pergunta=pergunta),
                }
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        indices = json.loads(resposta.choices[0].message.content or "{}")["indices"]
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
