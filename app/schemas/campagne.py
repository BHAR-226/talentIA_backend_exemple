"""Schémas Pydantic pour la gestion des Campagnes (CDC §6)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CampagneBase(BaseModel):
    """Champs communs à la création et à l'affichage d'une campagne."""

    intitule: str = Field(..., max_length=255, description="Intitulé de la campagne")
    departement: str | None = Field(None, max_length=255)
    date_limite: datetime | None = None
    nombre_postes: int = Field(
        default=1, ge=1, description="Nombre de postes à pourvoir (minimum 1)"
    )

    # Critères de cadrage de la campagne
    localisation: str | None = Field(None, max_length=255)
    competences: list[str] | None = Field(default_factory=list)
    experience: str | None = Field(None, max_length=100)
    langues: list[str] | None = Field(default_factory=list)
    niveau_etudes: str | None = Field(None, max_length=100)
    type_contrat: str | None = Field(None, max_length=100)
    salaire: str | None = Field(None, max_length=100)
    workflow: list[dict[str, Any]] | None = Field(default_factory=list)


class CampagneCreate(CampagneBase):
    """Schéma pour la création d'une campagne via POST."""

    pass


class CampagneUpdate(BaseModel):
    """Schéma pour la mise à jour partielle via PUT/PATCH.
    Tous les champs sont optionnels pour ne modifier que ce qui est transmis.
    """

    intitule: str | None = Field(None, max_length=255)
    departement: str | None = Field(None, max_length=255)
    date_limite: datetime | None = None
    nombre_postes: int | None = Field(None, ge=1)
    localisation: str | None = Field(None, max_length=255)
    competences: list[str] | None = None
    experience: str | None = Field(None, max_length=100)
    langues: list[str] | None = None
    niveau_etudes: str | None = Field(None, max_length=100)
    type_contrat: str | None = Field(None, max_length=100)
    salaire: str | None = Field(None, max_length=100)
    workflow: list[dict[str, Any]] | None = None


class CampagneResponse(CampagneBase):
    """Schéma renvoyé au Frontend lors de la lecture d'une campagne (GET)."""

    id: uuid.UUID
    entreprise_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
