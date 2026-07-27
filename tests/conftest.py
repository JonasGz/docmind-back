import io
import uuid

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import text

from app.config import settings
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


TABELAS = "users, documents, document_chunks, conversations, messages"


def pytest_configure() -> None:
    if "test" not in settings.database_url:
        pytest.exit(
            "DATABASE_URL não aponta para um banco de teste. "
            "Rode com: DATABASE_URL=...docmind_test uv run pytest",
            returncode=1,
        )


@pytest.fixture(autouse=True)
def limpar_banco():
    yield
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABELAS} CASCADE"))


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


class ModeloFalso:
    def __init__(self, resposta: str = "Resposta do modelo.", json: dict | None = None):
        self.modelo_embedding = "text-embedding-3-large"
        self.resposta = resposta
        self.json = json or {}
        self.completar_chamado = False

    def completar(self, mensagens: list[dict[str, str]]) -> str:
        self.completar_chamado = True
        return self.resposta

    def completar_json(self, prompt: str) -> dict:
        return self.json

    def embutir(self, textos: list[str]) -> list[list[float]]:
        return [[0.1] * 1536 for _ in textos]

    def embutir_um(self, texto: str) -> list[float]:
        return self.embutir([texto])[0]


@pytest.fixture
def llm_falso() -> ModeloFalso:
    return ModeloFalso()
