import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.rag.loader import PaginaExtraida

SEPARADORES_PADRAO = ["\n\n", "\n", ". ", " ", ""]

SEPARADORES_LEGISLATIVOS = [
    r"\n\s*Art\.\s*\d+",
    r"\n\s*§\s*\d+",
    r"\n\s*Parágrafo único",
    *SEPARADORES_PADRAO,
]

MARCADOR_ARTIGO = re.compile(r"\bArt\.\s*\d+", re.IGNORECASE)
MINIMO_ARTIGOS = 3


@dataclass
class ChunkExtraido:
    indice: int
    pagina: int
    conteudo: str


def e_legislativo(texto: str) -> bool:
    return len(MARCADOR_ARTIGO.findall(texto)) >= MINIMO_ARTIGOS


def dividir(paginas: list[PaginaExtraida]) -> list[ChunkExtraido]:
    legislativo = e_legislativo("\n".join(p.texto for p in paginas))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=SEPARADORES_LEGISLATIVOS if legislativo else SEPARADORES_PADRAO,
        is_separator_regex=legislativo,
        keep_separator="start",
    )

    chunks: list[ChunkExtraido] = []
    for pagina in paginas:
        for trecho in splitter.split_text(pagina.texto):
            chunks.append(
                ChunkExtraido(
                    indice=len(chunks), pagina=pagina.numero, conteudo=trecho
                )
            )

    return chunks
