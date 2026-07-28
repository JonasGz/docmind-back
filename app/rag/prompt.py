import re

from app.models import Message
from app.repositories.chunk import ChunkEncontrado

_ETIQUETA = re.compile(r"\[(\d+)\]")
_ETIQUETAS_COLADAS = re.compile(r"[ \t]*(?:\[\d+\])+")

SYSTEM_PROMPT = """Você é um assistente jurídico que responde exclusivamente com base nos documentos fornecidos.

Regras obrigatórias:
- Cite a fonte de cada afirmação usando o nome do documento como aparece no
  cabeçalho do contexto, seguido da página. Exemplo: (Contrato de Locação
  Comercial, p.4). Nunca escreva a palavra "Documento" no lugar do nome real.
- Logo após cada citação, acrescente a etiqueta entre colchetes do trecho que
  sustenta a afirmação, como aparece no contexto. Exemplo: (Contrato de Locação
  Comercial, p.4) [1]. Se mais de um trecho sustentar a mesma afirmação, use
  todas as etiquetas: [2][3]. Use apenas etiquetas presentes no contexto e não
  use etiqueta alguma para afirmações que os trechos não sustentam.
- Se documentos divergirem entre si, aponte a divergência explicitamente,
  indicando o que cada um estabelece.
- Se o contexto não sustentar a resposta, diga que não encontrou a informação
  nos documentos. Nunca preencha lacunas com conhecimento geral.
- Reporte o que os documentos dizem. Não recomende conduta nem forneça
  aconselhamento jurídico.
- Responda em português, de forma objetiva."""

SEM_CONTEXTO = (
    "Não encontrei informação sobre isso nos seus documentos. "
    "Verifique se o documento relevante foi enviado e indexado."
)


def montar_contexto(encontrados: list[ChunkEncontrado]) -> str:
    por_documento: dict[str, list[tuple[int, ChunkEncontrado]]] = {}
    for etiqueta, item in enumerate(encontrados, start=1):
        por_documento.setdefault(_cabecalho(item.documento), []).append(
            (etiqueta, item)
        )

    blocos = []
    for cabecalho, itens in por_documento.items():
        trechos = "\n".join(
            f"[{etiqueta}] (p.{i.chunk.page}) {i.chunk.content}"
            for etiqueta, i in sorted(itens, key=lambda par: par[1].chunk.page)
        )
        blocos.append(f"=== {cabecalho} ===\n{trechos}")

    return "\n\n".join(blocos)


def extrair_citados(
    texto: str, encontrados: list[ChunkEncontrado]
) -> list[ChunkEncontrado]:
    etiquetas = {int(n) for n in _ETIQUETA.findall(texto)}
    return [
        encontrados[n - 1]
        for n in sorted(etiquetas)
        if 1 <= n <= len(encontrados)
    ]


def remover_etiquetas(texto: str) -> str:
    return _ETIQUETAS_COLADAS.sub("", texto).strip()


def montar_mensagens(
    pergunta: str, encontrados: list[ChunkEncontrado], historico: list[Message]
) -> list[dict[str, str]]:
    mensagens = [{"role": "system", "content": SYSTEM_PROMPT}]

    mensagens.extend(
        {"role": m.role.value, "content": m.content} for m in historico
    )

    mensagens.append(
        {
            "role": "user",
            "content": (
                "CONTEXTO ENCONTRADO NOS SEUS DOCUMENTOS\n"
                "------------------------\n"
                f"{montar_contexto(encontrados)}\n"
                "------------------------\n\n"
                f"Pergunta: {pergunta}"
            ),
        }
    )

    return mensagens


def _cabecalho(documento) -> str:
    nome = documento.title or documento.filename
    if documento.identifiers:
        return f"{nome} — {' × '.join(documento.identifiers)}"
    return nome
