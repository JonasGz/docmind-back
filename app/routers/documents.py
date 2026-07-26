import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.config import settings
from app.dependencies import CurrentUser, DbSession
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DownloadUrlResponse,
)
from app.services.document_service import (
    DocumentError,
    DocumentNotFound,
    DocumentService,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload(
    arquivo: UploadFile, user: CurrentUser, db: DbSession
) -> DocumentResponse:
    if arquivo.content_type != "application/pdf":
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "apenas arquivos PDF"
        )

    conteudo = await arquivo.read()

    try:
        documento = DocumentService(db).upload(
            user.id, arquivo.filename or "documento.pdf", conteudo
        )
    except DocumentError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    return DocumentResponse.model_validate(documento)


@router.get("")
def listar(user: CurrentUser, db: DbSession) -> DocumentListResponse:
    documentos = DocumentService(db).listar(user.id)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in documentos]
    )


@router.get("/{document_id}")
def obter(document_id: uuid.UUID, user: CurrentUser, db: DbSession) -> DocumentResponse:
    try:
        documento = DocumentService(db).obter(document_id, user.id)
    except DocumentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return DocumentResponse.model_validate(documento)


@router.get("/{document_id}/download")
def download(
    document_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> DownloadUrlResponse:
    try:
        url = DocumentService(db).url_de_download(document_id, user.id)
    except DocumentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return DownloadUrlResponse(
        url=url, expires_in_seconds=settings.presigned_url_minutes * 60
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(document_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    try:
        DocumentService(db).deletar(document_id, user.id)
    except DocumentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
