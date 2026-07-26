from unittest.mock import MagicMock, patch

import pytest

from app.models import DocumentStatus, DocumentType
from app.rag import loader, splitter
from app.repositories.chunk import ChunkRepository
from app.repositories.document import DocumentRepository
from app.services import ingestion_service
from app.services.document_service import DocumentError, DocumentService
from tests.conftest import PDF_CONTRATO, PDF_SEM_TEXTO

METADADOS = ingestion_service.metadata.MetadadosExtraidos(
    title="Contrato de Prestação de Serviços",
    doc_type=DocumentType.CONTRATO,
    raw_doc_type="Contrato",
    identifiers=["ACME Ltda.", "Beta S.A."],
)


def _processar(db, usuario, embeddings_falsos, metadados=METADADOS, erro=None):
    documento = DocumentService(db).upload(usuario.id, "contrato.pdf", PDF_CONTRATO)
    alvo = {"side_effect": erro} if erro else {"return_value": metadados}

    with patch.object(
        ingestion_service, "EmbeddingService", return_value=embeddings_falsos
    ), patch.object(ingestion_service.metadata, "extrair", **alvo):
        ingestion_service.processar_documento(documento.id, usuario.id)

    db.expire_all()
    return DocumentRepository(db).get(documento.id, usuario.id)


def test_extrai_paginas_preservando_numero():
    paginas = loader.extrair_paginas(PDF_CONTRATO)

    assert [p.numero for p in paginas] == [1, 2]
    assert "CONTRATO" in paginas[0].texto
    assert "RESCISAO" in paginas[1].texto


def test_pdf_sem_texto_e_rejeitado():
    with pytest.raises(loader.PdfVazioError):
        loader.extrair_paginas(PDF_SEM_TEXTO)


def test_chunks_herdam_a_pagina_de_origem():
    chunks = splitter.dividir(loader.extrair_paginas(PDF_CONTRATO))

    assert {c.pagina for c in chunks} == {1, 2}
    assert [c.indice for c in chunks] == list(range(len(chunks)))
    assert all("RESCISAO" not in c.conteudo for c in chunks if c.pagina == 1)


def test_pipeline_indexa_e_grava_metadados(db, usuario_a, embeddings_falsos):
    documento = _processar(db, usuario_a, embeddings_falsos)

    assert documento.status == DocumentStatus.INDEXED
    assert documento.title == "Contrato de Prestação de Serviços"
    assert documento.doc_type == DocumentType.CONTRATO
    assert documento.raw_doc_type == "Contrato"
    assert documento.identifiers == ["ACME Ltda.", "Beta S.A."]
    assert documento.page_count == 2
    assert documento.chunk_count > 0

    gravados = ChunkRepository(db).contar_por_documento(documento.id, usuario_a.id)
    assert gravados == documento.chunk_count


def test_falha_de_metadados_nao_impede_indexacao(db, usuario_a, embeddings_falsos):
    documento = _processar(
        db, usuario_a, embeddings_falsos, erro=RuntimeError("LLM fora")
    )

    assert documento.status == DocumentStatus.INDEXED
    assert documento.title == "contrato.pdf"
    assert documento.doc_type == DocumentType.OUTRO
    assert documento.chunk_count > 0


def test_falha_de_embedding_marca_documento_como_falho(db, usuario_a):
    quebrado = MagicMock()
    quebrado.gerar.side_effect = RuntimeError("API indisponível")

    documento = _processar(db, usuario_a, quebrado)

    assert documento.status == DocumentStatus.FAILED
    assert "API indisponível" in documento.error_message
    assert ChunkRepository(db).contar_por_documento(documento.id, usuario_a.id) == 0


def test_upload_rejeita_arquivo_vazio(db, usuario_a):
    with pytest.raises(DocumentError):
        DocumentService(db).upload(usuario_a.id, "vazio.pdf", b"")


def test_upload_rejeita_arquivo_grande(db, usuario_a):
    with pytest.raises(DocumentError, match="limite"):
        DocumentService(db).upload(usuario_a.id, "grande.pdf", b"x" * (21 * 1024 * 1024))
