import pytest

from app.models import DocumentStatus, DocumentType
from app.rag import loader, splitter
from app.rag.loader import PaginaExtraida
from app.repositories.chunk import ChunkRepository
from app.repositories.document import DocumentRepository
from app.services import ingestion_service
from app.services.document_service import DocumentError, DocumentService
from tests.conftest import PDF_CONTRATO, PDF_SEM_TEXTO, ModeloFalso

METADADOS_JSON = {
    "title": "Contrato de Prestação de Serviços",
    "doc_type": "contrato",
    "raw_doc_type": "Contrato",
    "identifiers": ["ACME Ltda.", "Beta S.A."],
}


def _processar(db, usuario, llm, metadados=METADADOS_JSON):
    documento = DocumentService(db).upload(usuario.id, "contrato.pdf", PDF_CONTRATO)
    llm.json = metadados

    ingestion_service.processar_documento(documento.id, usuario.id, llm=llm)

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


LEI = """Art. 1º Esta Lei estabelece normas gerais de licitação.
Art. 2º Aplica-se a administração direta e indireta.
Art. 55. Os prazos mínimos para apresentação de propostas serão:
I - para aquisição de bens:
a) 8 dias úteis, no caso de menor preço;
b) 25 dias úteis, quando adotados critérios de técnica e preço;
Art. 56. A modalidade pregão segue o rito comum."""

CONTRATO = """CONTRATO DE PRESTACAO DE SERVICOS
De um lado ACME Ltda., de outro Beta S.A.
CLAUSULA PRIMEIRA - DO OBJETO
Consultoria juridica, observado o Art. 5 da Constituicao.
CLAUSULA SEGUNDA - DO PRAZO
Vigencia de 24 meses."""


def test_detecta_documento_legislativo():
    assert splitter.e_legislativo(LEI)


def test_contrato_que_cita_artigo_nao_e_legislativo():
    assert not splitter.e_legislativo(CONTRATO)


def test_chunks_de_lei_ancoram_no_comando_normativo():
    chunks = splitter.dividir([PaginaExtraida(numero=1, texto=LEI)])

    ancorados = [c for c in chunks if c.conteudo.strip().startswith(("Art.", "§"))]
    assert ancorados
    assert not any(c.conteudo.strip().startswith(("a)", "b)")) for c in chunks)


def test_pipeline_indexa_e_grava_metadados(db, usuario_a, llm_falso):
    documento = _processar(db, usuario_a, llm_falso)

    assert documento.status == DocumentStatus.INDEXED
    assert documento.title == "Contrato de Prestação de Serviços"
    assert documento.doc_type == DocumentType.CONTRATO
    assert documento.raw_doc_type == "Contrato"
    assert documento.identifiers == ["ACME Ltda.", "Beta S.A."]
    assert documento.page_count == 2
    assert documento.chunk_count > 0

    gravados = ChunkRepository(db).contar_por_documento(documento.id, usuario_a.id)
    assert gravados == documento.chunk_count


def test_falha_de_metadados_nao_impede_indexacao(db, usuario_a):
    class MetadadosQuebrados(ModeloFalso):
        def completar_json(self, prompt):
            raise RuntimeError("LLM fora")

    documento = _processar(db, usuario_a, MetadadosQuebrados())

    assert documento.status == DocumentStatus.INDEXED
    assert documento.title == "contrato.pdf"
    assert documento.doc_type == DocumentType.OUTRO
    assert documento.chunk_count > 0


def test_falha_de_embedding_marca_documento_como_falho(db, usuario_a):
    class EmbeddingQuebrado(ModeloFalso):
        def embutir(self, textos):
            raise RuntimeError("API indisponível")

    documento = _processar(db, usuario_a, EmbeddingQuebrado())

    assert documento.status == DocumentStatus.FAILED
    assert "API indisponível" in documento.error_message
    assert ChunkRepository(db).contar_por_documento(documento.id, usuario_a.id) == 0


def test_upload_rejeita_arquivo_vazio(db, usuario_a):
    with pytest.raises(DocumentError):
        DocumentService(db).upload(usuario_a.id, "vazio.pdf", b"")


def test_upload_rejeita_arquivo_grande(db, usuario_a):
    with pytest.raises(DocumentError, match="limite"):
        DocumentService(db).upload(usuario_a.id, "grande.pdf", b"x" * (21 * 1024 * 1024))
