import sys

from app.database.session import SessionLocal
from app.repositories.user import UserRepository
from app.services.auth_service import AuthService


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else "dev@docmind.local"

    with SessionLocal() as db:
        repo = UserRepository(db)
        usuario = repo.get_by_email(email) or repo.create(
            email, email.split("@")[0], None
        )
        db.commit()
        print(AuthService(db)._emitir_par(usuario.id).access_token)


if __name__ == "__main__":
    main()
