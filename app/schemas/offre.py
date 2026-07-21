"""Schémas Pydantic pour la gestion des Offres d'emploi (CDC §7)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StatutOffre, TypeContrat


class OffreBase(BaseModel):
    """Champs de base partagés par la création et l'affichage d'une offre."""

    titre: str = Field(..., max_length=255, description="Titre de l'offre d'emploi")
    description: str | None = Field(None, description="Description détaillée du poste et des missions")
    type_contrat: TypeContrat | None = Field(None, description="Type de contrat (CDI, CDD, Stage...)")
    localisation: str | None = Field(None, max_length=255, description="Lieu de travail")
    salaire_min: int | None = Field(None, ge=0, description="Salaire minimum")
    salaire_max: int | None = Field(None, ge=0, description="Salaire maximum")
    reception_ouverte: bool = Field(True, description="Indique si l'offre accepte encore des candidatures")
    champs_personnalises_def: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Questions/champs personnalisés configurés pour le formulaire de candidature",
    )


class OffreCreate(OffreBase):
    """Schéma pour la création d'une offre via POST.
    L'offre est liée à une campagne spécifique.
    """

    campagne_id: uuid.UUID
    statut: StatutOffre = Field(default=StatutOffre.brouillon)


class OffreUpdate(BaseModel):
    """Schéma pour la mise à jour partielle d'une offre (PUT/PATCH)."""

    titre: str | None = Field(None, max_length=255)
    description: str | None = None
    type_contrat: TypeContrat | None = None
    localisation: str | None = Field(None, max_length=255)
    salaire_min: int | None = Field(None, ge=0)
    salaire_max: int | None = Field(None, ge=0)
    statut: StatutOffre | None = None
    reception_ouverte: bool | None = None
    champs_personnalises_def: list[dict[str, Any]] | None = None


class ReceptionUpdate(BaseModel):
    """Schéma spécifique pour l'action du bouton 'Arrêter/Rouvrir' les candidatures."""

    reception_ouverte: bool = Field(..., description="True pour ouvrir, False pour arrêter la réception")


class OffreResponse(OffreBase):
    """Schéma renvoyé au Frontend lors de la lecture d'une offre (GET)."""

    id: uuid.UUID
    campagne_id: uuid.UUID
    createur_id: uuid.UUID | None = None
    statut: StatutOffre
    date_publication: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)