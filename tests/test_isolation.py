from app.repositories.chunk import ChunkRepository
from app.repositories.document import DocumentRepository
from app.services import ingestion_service
from app.services.document_service import DocumentService
from tests.conftest import PDF_CONTRATO, auth


def _documento_indexado(db, usuario, llm_falso):
    documento = DocumentService(db).upload(usuario.id, "contrato.pdf", PDF_CONTRATO)
    ingestion_service.processar_documento(documento.id, usuario.id, llm=llm_falso)
    db.expire_all()
    return documento


def test_busca_vetorial_nao_atravessa_usuarios(
    db, usuario_a, usuario_b, llm_falso
):
    _documento_indexado(db, usuario_a, llm_falso)

    chunks = ChunkRepository(db)
    vetor = [0.1] * 1536

    assert chunks.search(usuario_a.id, vetor, k=10, threshold=0.0)
    assert chunks.search(usuario_b.id, vetor, k=10, threshold=0.0) == []


def test_repositorio_nao_entrega_documento_de_outro(
    db, usuario_a, usuario_b, llm_falso
):
    documento = _documento_indexado(db, usuario_a, llm_falso)
    repo = DocumentRepository(db)

    assert repo.get(documento.id, usuario_a.id) is not None
    assert repo.get(documento.id, usuario_b.id) is None
    assert repo.list_by_user(usuario_b.id) == []


def test_contagem_de_chunks_respeita_dono(
    db, usuario_a, usuario_b, llm_falso
):
    documento = _documento_indexado(db, usuario_a, llm_falso)
    chunks = ChunkRepository(db)

    assert chunks.contar_por_documento(documento.id, usuario_a.id) > 0
    assert chunks.contar_por_documento(documento.id, usuario_b.id) == 0


def test_rotas_de_documento_devolvem_404_para_outro_usuario(
    client, db, usuario_a, usuario_b, llm_falso
):
    documento = _documento_indexado(db, usuario_a, llm_falso)
    cabecalho_b = auth(db, usuario_b)

    assert client.get(f"/documents/{documento.id}", headers=cabecalho_b).status_code == 404
    assert (
        client.get(f"/documents/{documento.id}/download", headers=cabecalho_b).status_code
        == 404
    )
    assert (
        client.delete(f"/documents/{documento.id}", headers=cabecalho_b).status_code == 404
    )
    assert client.get("/documents", headers=cabecalho_b).json()["items"] == []


def test_rotas_de_conversa_devolvem_404_para_outro_usuario(
    client, db, usuario_a, usuario_b
):
    criada = client.post("/conversations", headers=auth(db, usuario_a), json={})
    conversa_id = criada.json()["id"]
    cabecalho_b = auth(db, usuario_b)

    assert (
        client.get(f"/conversations/{conversa_id}/messages", headers=cabecalho_b).status_code
        == 404
    )
    assert (
        client.post(
            f"/conversations/{conversa_id}/messages",
            headers=cabecalho_b,
            json={"content": "oi"},
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/conversations/{conversa_id}", headers=cabecalho_b).status_code == 404
    )
    assert client.get("/conversations", headers=cabecalho_b).json()["items"] == []


def test_rotas_exigem_autenticacao(client):
    assert client.get("/documents").status_code == 401
    assert client.get("/conversations").status_code == 401
    assert client.get("/auth/me").status_code == 401
