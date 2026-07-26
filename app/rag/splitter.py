from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.rag.loader import PaginaExtraida


@dataclass
class ChunkExtraido:
    indice: int
    pagina: int
    conteudo: str


def dividir(paginas: list[PaginaExtraida]) -> list[ChunkExtraido]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
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
