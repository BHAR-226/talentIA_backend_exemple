"""
Schémas Pydantic des candidatures.

Ils définissent :
- les données reçues par l'API
- les données renvoyées au frontend Next.js

Les modèles ORM SQLAlchemy sont convertis grâce à
ConfigDict(from_attributes=True).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import StatutCandidature


# ==========================================================
# Création d'une candidature
# ==========================================================

class CandidatureCreate(BaseModel):
    """
    Données envoyées lors d'une candidature.

    Le CV est envoyé séparément (UploadFile) dans la route FastAPI,
    il n'apparaît donc pas ici.
    """

    offre_id: UUID
    lettre_motivation: str | None = None
    champs_personnalises: dict[str, Any] = {}


# ==========================================================
# Mise à jour du statut
# ==========================================================

class CandidatureUpdateStatut(BaseModel):
    """
    Changement de statut depuis le Kanban recruteur.
    """

    statut: StatutCandidature


# ==========================================================
# Réponse API
# ==========================================================

class CandidatureResponse(BaseModel):
    """
    Objet renvoyé au frontend.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID

    offre_id: UUID
    candidat_id: UUID

    statut: StatutCandidature
    date_soumission: datetime

    lettre_motivation: str | None

    cv_url: str | None

    champs_personnalises: dict[str, Any]

    score_global: int | None

    evaluation_ia: dict[str, Any] | None

    created_at: datetime
    updated_at: datetime