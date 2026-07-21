"""Environnement Alembic — branché sur `Base.metadata` et l'URL de la config.

Importer `app.models` enregistre tous les modèles auprès de `Base.metadata`,
ce qui permet l'autogénération des migrations (`alembic revision --autogenerate`).
"""

import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

# Charge explicitement les variables définies dans le fichier .env
load_dotenv()

import app.models  # noqa: F401  (enregistre tous les modèles sur Base.metadata)
from app.core.config import settings
from app.core.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Priorité à l'URL du .env si elle existe, sinon on utilise la config de l'app
db_url = os.getenv("DATABASE_URL") or settings.database_url

# Affichage de l'URL dans la console pour valider la connexion lors de l'exécution
print(f"--> [Alembic] Connexion avec l'URL : {db_url}")

config.set_main_option("sqlalchemy.url", db_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
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
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()