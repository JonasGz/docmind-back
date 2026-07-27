import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenPair

TokenType = Literal["access", "refresh"]


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def login_with_google(self, token: str) -> TokenPair:
        claims = self._verificar_google_token(token)
        user = self._encontrar_ou_criar(claims)
        self.db.commit()
        return self._emitir_par(user.id)

    def refresh(self, token: str) -> TokenPair:
        payload = self._decodificar(token, esperado="refresh")
        user = self.users.get_by_id(uuid.UUID(payload["sub"]))
        if user is None:
            raise AuthError("usuário não encontrado")
        return self._emitir_par(user.id)

    def usuario_do_token(self, token: str) -> User:
        payload = self._decodificar(token, esperado="access")
        user = self.users.get_by_id(uuid.UUID(payload["sub"]))
        if user is None:
            raise AuthError("usuário não encontrado")
        return user

    def _verificar_google_token(self, token: str) -> dict:
        if not settings.google_client_id:
            raise AuthError("GOOGLE_CLIENT_ID não configurado")

        try:
            claims = google_id_token.verify_oauth2_token(
                token, google_requests.Request(), settings.google_audiences
            )
        except ValueError as exc:
            raise AuthError("id_token inválido") from exc

        if not claims.get("email_verified"):
            raise AuthError("email não verificado pelo Google")

        return claims

    def _encontrar_ou_criar(self, claims: dict) -> User:
        email = claims["email"]
        google_sub = claims["sub"]

        user = self.users.get_by_email(email)
        if user is None:
            return self.users.create(email, claims.get("name"), google_sub)

        if user.google_sub is None:
            user.google_sub = google_sub
        return user

    def _emitir_par(self, user_id: uuid.UUID) -> TokenPair:
        return TokenPair(
            access_token=self._gerar(
                user_id, "access", timedelta(minutes=settings.access_token_minutes)
            ),
            refresh_token=self._gerar(
                user_id, "refresh", timedelta(days=settings.refresh_token_days)
            ),
        )

    def _gerar(self, user_id: uuid.UUID, tipo: TokenType, validade: timedelta) -> str:
        agora = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "type": tipo,
            "iat": agora,
            "exp": agora + validade,
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    def _decodificar(self, token: str, esperado: TokenType) -> dict:
        try:
            payload = jwt.decode(
                token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("token expirado") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthError("token inválido") from exc

        if payload.get("type") != esperado:
            raise AuthError(f"esperado token do tipo {esperado}")

        return payload
