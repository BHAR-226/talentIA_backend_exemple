"""Environnement Alembic — branché sur `Base.metadata` et l'URL de la config.

Importer `app.models` enregistre tous les modèles auprès de `Base.metadata`,
ce qui permet l'autogénération des migrations (`alembic revision --autogenerate`).
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# ==========================================================
# Configuration du chemin
# ==========================================================

# Ajouter le répertoire parent au sys.path pour importer app
sys.path.insert(0, str(Path(__file__).parent.parent))

# ==========================================================
# Chargement des variables d'environnement
# ==========================================================

# Chercher le fichier .env dans le répertoire parent
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ .env chargé depuis: {env_file}")
else:
    load_dotenv()
    print("⚠️ Aucun fichier .env trouvé, utilisation des variables d'environnement")

# ==========================================================
# Configuration Alembic
# ==========================================================

# Créer l'objet de configuration
config = context.config

# Charger la configuration des logs depuis le fichier alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ==========================================================
# Import des modèles
# ==========================================================

# Importer app.models enregistre tous les modèles sur Base.metadata
import app.models  # noqa: F401, E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402

# ==========================================================
# Configuration de la base de données
# ==========================================================

# Priorité à l'URL du .env si elle existe, sinon on utilise la config de l'app
db_url = os.getenv("DATABASE_URL") or settings.database_url

# Vérifier que l'URL est définie
if not db_url:
    raise ValueError("❌ DATABASE_URL non définie. Vérifiez votre fichier .env")

# Affichage de l'URL dans la console pour valider la connexion (masquer le mot de passe)
db_url_display = db_url.replace(
    db_url.split("@")[0].split(":")[-1] if "@" in db_url else "",
    "***"
)
print(f"🔗 [Alembic] Connexion avec l'URL : {db_url_display}")

# Définir l'URL dans la configuration Alembic
config.set_main_option("sqlalchemy.url", db_url)

# Métadonnées cibles
target_metadata = Base.metadata

# ==========================================================
# Fonctions de migration
# ==========================================================

def run_migrations_offline() -> None:
    """Exécute les migrations en mode offline."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Exécute les migrations en mode online."""
    # Créer un moteur de base de données à partir de la configuration
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # Pour les migrations avec des tables existantes
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ==========================================================
# Point d'entrée
# ==========================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()