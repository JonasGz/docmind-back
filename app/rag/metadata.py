import json
import logging
from dataclasses import dataclass, field

from openai import OpenAI

from app.config import settings
from app.models import DocumentType

logger = logging.getLogger(__name__)

CHUNKS_ANALISADOS = 3

PROMPT = """Analise o início deste documento jurídico brasileiro e extraia seus metadados.

--- DOCUMENTO ---
{trecho}
--- FIM ---

Responda apenas com JSON neste formato:
{{"title": "...", "doc_type": "...", "raw_doc_type": "...", "identifiers": ["...", "..."]}}

- title: o título do documento, conciso
- raw_doc_type: a espécie exata como aparece no documento, sem generalizar
  (ex: "Portaria", "Acórdão", "Termo Aditivo", "Contestação", "Nota Técnica")
- doc_type: a categoria ampla, um de {tipos}, conforme a tabela abaixo
- identifiers: o que identifica unicamente o documento, conforme o doc_type

| doc_type       | espécies                                          | identifiers                              |
|----------------|---------------------------------------------------|------------------------------------------|
| norma          | lei, decreto, decreto-lei, portaria, resolução,   | número/ano e órgão ou nome comum         |
|                | instrução normativa, ato normativo, circular      | ex: ["Lei 8.112/90", "Estatuto do Servidor"] |
| jurisprudencia | acórdão, sentença, despacho, decisão              | processo, tribunal, relator              |
|                |                                                   | ex: ["RE 574.706", "STF"]                |
| sumula         | súmula, súmula vinculante                         | número e tribunal                        |
|                |                                                   | ex: ["Súmula 331", "TST"]                |
| contrato       | contrato, convênio, termo aditivo, procuração,    | partes envolvidas                        |
|                | notificação extrajudicial                         | ex: ["ACME Ltda.", "Beta S.A."]          |
| parecer        | parecer, nota técnica, recomendação               | número e órgão emissor                   |
|                |                                                   | ex: ["Parecer 12/2023", "AGU"]           |
| peticao        | petição inicial, contestação, recurso, embargos   | processo, vara/tribunal, partes          |
|                |                                                   | ex: ["0001234-56.2024.8.26.0100", "3ª Vara Cível"] |
| comunicacao    | ofício, memorando, comunicado                     | número, remetente, destinatário          |
|                |                                                   | ex: ["Ofício 45/2024", "Secretaria de Saúde"] |
| edital         | edital, aviso de licitação, chamamento público    | número, órgão, objeto                    |
|                |                                                   | ex: ["Edital 07/2024", "Prefeitura de SP"] |
| outro          | qualquer outro                                    | o que for distintivo                     |

Use lista vazia se não houver identificadores claros."""


@dataclass
class MetadadosExtraidos:
    title: str | None = None
    doc_type: DocumentType | None = None
    raw_doc_type: str | None = None
    identifiers: list[str] = field(default_factory=list)


def extrair(trechos: list[str], client: OpenAI | None = None) -> MetadadosExtraidos:
    if not trechos:
        return MetadadosExtraidos()

    cliente = client or OpenAI(api_key=settings.openai_api_key)
    tipos = ", ".join(t.value for t in DocumentType)
    prompt = PROMPT.format(
        trecho="\n".join(trechos[:CHUNKS_ANALISADOS]), tipos=tipos
    )

    try:
        resposta = cliente.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        dados = json.loads(resposta.choices[0].message.content or "{}")
    except Exception:
        logger.warning("extração de metadados falhou", exc_info=True)
        return MetadadosExtraidos()

    return MetadadosExtraidos(
        title=_texto(dados.get("title")),
        doc_type=_tipo(dados.get("doc_type")),
        raw_doc_type=_texto(dados.get("raw_doc_type")),
        identifiers=_identificadores(dados.get("identifiers")),
    )


def _texto(valor: object) -> str | None:
    return valor.strip() if isinstance(valor, str) and valor.strip() else None


def _tipo(valor: object) -> DocumentType | None:
    try:
        return DocumentType(valor)
    except ValueError:
        return None


def _identificadores(valor: object) -> list[str]:
    if not isinstance(valor, list):
        return []
    return [i.strip() for i in valor if isinstance(i, str) and len(i.strip()) >= 3]
