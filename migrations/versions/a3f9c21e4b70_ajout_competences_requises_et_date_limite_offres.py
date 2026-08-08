"""ajout competences_requises et date_limite sur la table offres

Le modèle Offre a été enrichi (backend rattrapé) avec :
- `competences_requises` : compétences attendues pour le poste, stockées sous
  forme de liste d'objets `{libelle, obligatoire}` (aligné sur le frontend et
  l'entité COMPETENCE_REQUISE du CDC §7).
- `date_limite` : date limite de réception des candidatures (P2.6), indépendante
  de la date_limite de la campagne.

Revision ID: a3f9c21e4b70
Revises: 01e385a70aa0
Create Date: 2026-08-04 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3f9c21e4b70"
down_revision: str | None = "01e385a70aa0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "offres",
        sa.Column(
            "competences_requises",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment="Compétences requises pour le poste (libellé + obligatoire)",
        ),
    )
    op.add_column(
        "offres",
        sa.Column(
            "date_limite",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Date limite de réception des candidatures",
        ),
    )


def downgrade() -> None:
    op.drop_column("offres", "date_limite")
    op.drop_column("offres", "competences_requises")
