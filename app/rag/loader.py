import io
from dataclasses import dataclass

from pypdf import PdfReader


@dataclass
class PaginaExtraida:
    numero: int
    texto: str


class PdfVazioError(Exception):
    pass


def extrair_paginas(conteudo: bytes) -> list[PaginaExtraida]:
    leitor = PdfReader(io.BytesIO(conteudo))

    paginas = [
        PaginaExtraida(numero=indice, texto=texto)
        for indice, pagina in enumerate(leitor.pages, start=1)
        if (texto := (pagina.extract_text() or "").strip())
    ]

    if not paginas:
        raise PdfVazioError(
            "nenhum texto extraído: o PDF pode ser digitalizado e exigir OCR"
        )

    return paginas
