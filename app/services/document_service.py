import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document
from app.repositories.document import DocumentRepository
from app.storage.s3 import storage


class DocumentError(Exception):
    pass


class DocumentNotFound(DocumentError):
    pass


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.documentos = DocumentRepository(db)

    def upload(self, user_id: uuid.UUID, filename: str, conteudo: bytes) -> Document:
        if not conteudo:
            raise DocumentError("arquivo vazio")

        if len(conteudo) > settings.max_upload_mb * 1024 * 1024:
            raise DocumentError(
                f"arquivo excede o limite de {settings.max_upload_mb}MB"
            )

        documento = self.documentos.create(user_id, filename, storage_key="")
        chave = f"{user_id}/documents/{documento.id}.pdf"

        storage.upload(chave, conteudo, "application/pdf")
        documento.storage_key = chave
        self.db.commit()

        return documento

    def listar(self, user_id: uuid.UUID) -> list[Document]:
        self.documentos.marcar_travados_como_falha(user_id)
        self.db.commit()
        return self.documentos.list_by_user(user_id)

    def obter(self, document_id: uuid.UUID, user_id: uuid.UUID) -> Document:
        documento = self.documentos.get(document_id, user_id)
        if documento is None:
            raise DocumentNotFound("documento não encontrado")
        return documento

    def url_de_download(self, document_id: uuid.UUID, user_id: uuid.UUID) -> str:
        documento = self.obter(document_id, user_id)
        return storage.url_temporaria(documento.storage_key, documento.filename)

    def deletar(self, document_id: uuid.UUID, user_id: uuid.UUID) -> None:
        documento = self.obter(document_id, user_id)

        storage.apagar(documento.storage_key)
        self.documentos.delete(documento)
        self.db.commit()
