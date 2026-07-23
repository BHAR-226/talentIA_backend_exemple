"""ajout soft delete (deleted_at/deleted_by) sur campagnes, offres, candidatures

Les modèles Campagne, Offre et Candidature référencent `deleted_at` / `soft_delete()`
dans plusieurs routes et services (filtrage des enregistrements actifs, suppression
logique) alors que le SoftDeleteMixin n'avait jamais été appliqué à ces modèles.
Cette migration ajoute les colonnes manquantes en base pour que le code applicatif
(déjà corrigé pour hériter de SoftDeleteMixin) fonctionne réellement.

Revision ID: 01e385a70aa0
Revises: c1f0d928c5bc
Create Date: 2026-07-23 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "01e385a70aa0"
down_revision = "c1f0d928c5bc"
branch_labels = None
depends_on = None


TABLES = ("campagnes", "offres", "candidatures")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column(
                "deleted_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="Date et heure de la suppression logique",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "deleted_by",
                sa.UUID(),
                nullable=True,
                comment="ID de l'utilisateur qui a effectué la suppression",
            ),
        )
        op.create_index(
            f"ix_{table}_deleted_at",
            table,
            ["deleted_at"],
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_deleted_at", table_name=table)
        op.drop_column(table, "deleted_by")
        op.drop_column(table, "deleted_at")
