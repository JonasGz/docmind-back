import math
import uuid

from app.models import Document, DocumentChunk, DocumentStatus
from app.repositories.chunk import ChunkRepository

CONSULTA = [1.0, 0.0] + [0.0] * 1534


def _embedding_com_score(score: float) -> list[float]:
    angulo = math.acos(score)
    return [math.cos(angulo), math.sin(angulo)] + [0.0] * 1534


def _indexar(db, usuario, scores: list[float]) -> Document:
    documento = Document(
        user_id=usuario.id,
        filename="acervo.pdf",
        storage_key=f"{usuario.id}/documents/{uuid.uuid4()}.pdf",
        status=DocumentStatus.INDEXED,
    )
    db.add(documento)
    db.flush()

    db.add_all(
        DocumentChunk(
            document_id=documento.id,
            user_id=usuario.id,
            page=1,
            chunk_index=indice,
            content=f"trecho com score {score}",
            embedding=_embedding_com_score(score),
            embedding_model="text-embedding-3-large",
        )
        for indice, score in enumerate(scores)
    )
    db.commit()
    return documento


def test_score_do_embedding_de_teste_bate_com_o_pedido(db, usuario_a):
    _indexar(db, usuario_a, [0.81, 0.50])

    encontrados = ChunkRepository(db).search(
        usuario_a.id, CONSULTA, k=10, threshold=0.0
    )

    assert [round(e.score, 2) for e in encontrados] == [0.81, 0.50]


def test_limiar_nao_consome_as_vagas_de_k(db, usuario_a):
    _indexar(db, usuario_a, [0.81, 0.44, 0.41, 0.38, 0.36, 0.58, 0.55, 0.52])

    encontrados = ChunkRepository(db).search(
        usuario_a.id, CONSULTA, k=5, threshold=0.50
    )

    assert [round(e.score, 2) for e in encontrados] == [0.81, 0.58, 0.55, 0.52]


def test_k_limita_o_que_passou_no_limiar(db, usuario_a):
    _indexar(db, usuario_a, [0.90, 0.85, 0.80, 0.75, 0.70, 0.65])

    encontrados = ChunkRepository(db).search(
        usuario_a.id, CONSULTA, k=3, threshold=0.50
    )

    assert [round(e.score, 2) for e in encontrados] == [0.90, 0.85, 0.80]


def test_nenhum_chunk_acima_do_limiar_devolve_vazio(db, usuario_a):
    _indexar(db, usuario_a, [0.40, 0.30, 0.20])

    encontrados = ChunkRepository(db).search(
        usuario_a.id, CONSULTA, k=5, threshold=0.50
    )

    assert encontrados == []


def test_chunk_exatamente_no_limiar_passa(db, usuario_a):
    _indexar(db, usuario_a, [0.50])

    encontrados = ChunkRepository(db).search(
        usuario_a.id, CONSULTA, k=5, threshold=0.50
    )

    assert len(encontrados) == 1
