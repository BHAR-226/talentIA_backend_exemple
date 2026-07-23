"""Connexion à la base de données et session SQLAlchemy 2.0.

`Base` est la classe déclarative dont héritent tous les modèles (voir
`app/models`). `get_db` est la dépendance FastAPI qui fournit une session par
requête et la referme proprement.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings

logger = logging.getLogger("talentia.database")


# ==========================================================
# Configuration du moteur SQLAlchemy
# ==========================================================

def create_database_engine() -> Engine:
    """Crée et configure le moteur SQLAlchemy."""
    
    # Options de pool de connexions
    pool_options = {
        "pool_size": 10,                 # Nombre de connexions dans le pool
        "max_overflow": 20,              # Connexions supplémentaires autorisées
        "pool_timeout": 30,              # Temps d'attente pour une connexion (secondes)
        "pool_recycle": 3600,            # Recyclage des connexions après 1 heure
        "pool_pre_ping": True,           # Vérifier la connexion avant utilisation
    }
    
    # Options d'engine
    engine_options = {
        "echo": settings.debug,          # Log des requêtes SQL en dev
        "future": True,                  # Utiliser la nouvelle syntaxe SQLAlchemy 2.0
        "poolclass": QueuePool,          # Utiliser le pool de connexions
    }
    
    # Ajouter les options du pool
    engine_options.update(pool_options)
    
    engine = create_engine(
        settings.database_url,
        **engine_options,
    )
    
    # Ajouter un listener pour logger les connexions
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_connection, connection_record):
        logger.debug("Nouvelle connexion à la base de données établie")
    
    @event.listens_for(engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        logger.debug("Connexion récupérée du pool")
    
    return engine


# Créer le moteur
engine = create_database_engine()

# Créer la session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,  # Important : ne pas expirer les objets après commit
)


# ==========================================================
# Base de données déclarative
# ==========================================================

class Base(DeclarativeBase):
    """Classe de base déclarative partagée par tous les modèles."""
    
    # À implémenter plus tard pour le soft delete automatique
    # __abstract__ = True
    
    def __repr__(self) -> str:
        """Représentation de l'objet pour le logging."""
        return f"<{self.__class__.__name__} id={getattr(self, 'id', None)}>"


# ==========================================================
# Dépendance FastAPI
# ==========================================================

def get_db() -> Generator[Session, None, None]:
    """
    Dépendance FastAPI pour obtenir une session de base de données.
    
    Yields:
        Session: Une session SQLAlchemy pour la requête en cours.
    
    Notes:
        La session est automatiquement fermée à la fin de la requête.
        Les transactions sont gérées automatiquement via le contexte.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Commit automatique si aucune exception
    except Exception:
        db.rollback()  # Rollback en cas d'erreur
        raise
    finally:
        db.close()


# ==========================================================
# Gestionnaire de transactions (optionnel)
# ==========================================================

@contextmanager
def transaction(db: Session) -> Generator[Session, None, None]:
    """
    Gestionnaire de transaction pour une session.
    
    Usage:
        with transaction(db) as session:
            session.add(obj)
            # Commit automatique à la sortie
            # Rollback automatique en cas d'exception
    
    Args:
        db: Session SQLAlchemy
    
    Yields:
        Session: La session à utiliser
    """
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


# ==========================================================
# Utilitaires pour le développement
# ==========================================================

def create_tables() -> None:
    """Crée toutes les tables en base de données."""
    logger.info("Création des tables de la base de données...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables créées avec succès")


def drop_tables() -> None:
    """Supprime toutes les tables de la base de données (⚠️ DANGER)."""
    if settings.environment == "production":
        raise RuntimeError("⚠️ Impossible de supprimer les tables en production !")
    
    logger.warning("⚠️ Suppression de toutes les tables de la base de données...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("Tables supprimées")


def get_db_stats() -> dict:
    """Récupère les statistiques de la base de données."""
    try:
        db = SessionLocal()
        # Compter les tables
        result = db.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
        )
        table_count = result.scalar()
        
        result = db.execute("SELECT COUNT(*) FROM information_schema.columns")
        column_count = result.scalar()
        
        return {
            "table_count": table_count,
            "column_count": column_count,
            "connection_count": len(engine.pool.checkedin()),
            "engine": str(engine.url),
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


# ==========================================================
# Initialisation (optionnelle au démarrage)
# ==========================================================

def init_db(create_tables_if_missing: bool = False) -> None:
    """Initialise la base de données au démarrage."""
    if create_tables_if_missing and settings.environment != "production":
        create_tables()
    
    logger.info(f"✅ Base de données connectée : {engine.url}")
    logger.info(f"   Pool size: {engine.pool.size()}, Overflow: {engine.pool.overflow()}")