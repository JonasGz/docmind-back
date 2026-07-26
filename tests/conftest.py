import io
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import text

from app.database.session import SessionLocal, engine
from app.main import app
from app.models import User
from app.repositories.user import UserRepository
from app.services.auth_service import AuthService

def _gerar_pdf(paginas: list[list[str]]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    for linhas in paginas:
        altura = 780
        for linha in linhas:
            pdf.drawString(70, altura, linha)
            altura -= 16
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


PDF_CONTRATO = _gerar_pdf(
    [
        [
            "CONTRATO DE PRESTACAO DE SERVICOS",
            "De um lado ACME Ltda., denominada CONTRATANTE, e de outro",
            "Beta Servicos S.A., denominada CONTRATADA.",
            "CLAUSULA PRIMEIRA - A CONTRATADA prestara consultoria juridica.",
        ],
        [
            "CLAUSULA SEGUNDA - DA RESCISAO",
            "A rescisao antecipada implicara multa de 20% do valor restante.",
        ],
    ]
)

PDF_SEM_TEXTO = _gerar_pdf([[]])


@pytest.fixture(autouse=True)
def limpar_banco():
    yield
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE users, documents, document_chunks, conversations, messages CASCADE")
        )


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(app)


def _criar_usuario(db, email: str) -> User:
    usuario = UserRepository(db).create(email, email.split("@")[0], str(uuid.uuid4()))
    db.commit()
    return usuario


@pytest.fixture
def usuario_a(db) -> User:
    return _criar_usuario(db, "a@teste.dev")


@pytest.fixture
def usuario_b(db) -> User:
    return _criar_usuario(db, "b@teste.dev")


def auth(db, usuario: User) -> dict[str, str]:
    token = AuthService(db)._emitir_par(usuario.id).access_token
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def embeddings_falsos():
    servico = MagicMock()
    servico.gerar = lambda textos: [[0.1] * 1536 for _ in textos]
    servico.gerar_um = lambda texto: [0.1] * 1536
    servico.modelo = "text-embedding-3-large"
    return servico
