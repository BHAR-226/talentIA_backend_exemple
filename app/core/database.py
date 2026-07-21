"""Connexion à la base de données et session SQLAlchemy 2.0.

`Base` est la classe déclarative dont héritent tous les modèles (voir
`app/models`). `get_db` est la dépendance FastAPI qui fournit une session par
requête et la referme proprement.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, echo=settings.debug)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Classe de base déclarative partagée par tous les modèles."""


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
