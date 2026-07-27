import logging
import uuid

from app.database.session import SessionLocal
from app.llm import Modelo
from app.models import DocumentStatus
from app.rag import loader, metadata, splitter
from app.repositories.chunk import ChunkRepository
from app.repositories.document import DocumentRepository
from app.storage.s3 import Storage, storage as storage_padrao

logger = logging.getLogger(__name__)


def processar_documento(
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    llm: Modelo | None = None,
    storage: Storage | None = None,
) -> None:
    llm = llm or Modelo()
    storage = storage or storage_padrao

    with SessionLocal() as db:
        documentos = DocumentRepository(db)
        documento = documentos.get(document_id, user_id)
        if documento is None:
            logger.warning("documento %s não encontrado", document_id)
            return

        try:
            conteudo = storage.baixar(documento.storage_key)
            paginas = loader.extrair_paginas(conteudo)
            chunks = splitter.dividir(paginas)

            try:
                extraidos = metadata.extrair([c.conteudo for c in chunks], llm=llm)
            except Exception:
                logger.warning("extração de metadados falhou", exc_info=True)
                extraidos = metadata.MetadadosExtraidos()

            vetores = llm.embutir([c.conteudo for c in chunks])

            ChunkRepository(db).create_many(
                document_id=documento.id,
                user_id=documento.user_id,
                chunks=chunks,
                embeddings=vetores,
                embedding_model=llm.modelo_embedding,
            )

            documento.title = extraidos.title or documento.filename
            documento.doc_type = extraidos.doc_type
            documento.raw_doc_type = extraidos.raw_doc_type
            documento.identifiers = extraidos.identifiers
            documento.page_count = len(paginas)
            documento.chunk_count = len(chunks)
            documento.status = DocumentStatus.INDEXED
            db.commit()

        except Exception as exc:
            logger.exception("falha ao processar documento %s", document_id)
            db.rollback()
            _marcar_falha(db, document_id, user_id, str(exc))


def _marcar_falha(db, document_id: uuid.UUID, user_id: uuid.UUID, erro: str) -> None:
    documento = DocumentRepository(db).get(document_id, user_id)
    if documento is None:
        return
    documento.status = DocumentStatus.FAILED
    documento.error_message = erro[:500]
    db.commit()
