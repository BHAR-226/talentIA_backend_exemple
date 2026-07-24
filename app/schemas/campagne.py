"""Schémas Pydantic pour la gestion des Campagnes (CDC §6)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import TypeContrat


class CampagneBase(BaseModel):
    """Champs communs à la création et à l'affichage d'une campagne."""

    intitule: str = Field(
        min_length=1,
        max_length=255,
        description="Intitulé de la campagne"
    )
    departement: str | None = Field(
        default=None,
        max_length=255,
        description="Département ou service concerné"
    )
    date_limite: datetime | None = Field(
        default=None,
        description="Date limite de la campagne"
    )
    nombre_postes: int = Field(
        default=1,
        ge=1,
        le=1000,
        description="Nombre de postes à pourvoir"
    )

    # Critères de cadrage de la campagne
    localisation: str | None = Field(
        default=None,
        max_length=255,
        description="Localisation du poste"
    )
    competences: list[str] = Field(
        default_factory=list,
        description="Compétences requises"
    )
    experience_requise: str | None = Field(
        default=None,
        max_length=100,
        description="Expérience requise (ex: 3-5 ans)"
    )
    langues: list[str] = Field(
        default_factory=list,
        description="Langues requises"
    )
    niveau_etudes: str | None = Field(
        default=None,
        max_length=100,
        description="Niveau d'études requis"
    )
    type_contrat: TypeContrat | None = Field(
        default=None,
        description="Type de contrat proposé"
    )
    salaire_min: int | None = Field(
        default=None,
        ge=0,
        description="Salaire minimum proposé"
    )
    salaire_max: int | None = Field(
        default=None,
        ge=0,
        description="Salaire maximum proposé"
    )

    # Gestion de la campagne
    recruteurs_responsables: list[uuid.UUID] = Field(
        default_factory=list,
        description="Liste des IDs des recruteurs responsables"
    )
    description: str | None = Field(
        default=None,
        description="Description détaillée de la campagne"
    )
    workflow: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Workflow personnalisé de la campagne"
    )

    @field_validator('salaire_min', 'salaire_max')
    @classmethod
    def validate_salaire(cls, v: int | None) -> int | None:
        """Valide que le salaire est positif."""
        if v is not None and v < 0:
            raise ValueError('Le salaire doit être positif')
        return v

    @field_validator('salaire_min', 'salaire_max')
    @classmethod
    def validate_salaire_range(cls, v: int | None, info) -> int | None:
        """Valide que le salaire min est inférieur au salaire max."""
        if 'salaire_min' in info.data and 'salaire_max' in info.data:
            min_val = info.data.get('salaire_min')
            max_val = info.data.get('salaire_max')
            if min_val is not None and max_val is not None and min_val > max_val:
                raise ValueError('Le salaire minimum doit être inférieur au maximum')
        return v


class CampagneCreate(CampagneBase):
    """Schéma pour la création d'une campagne via POST."""
    pass


class CampagneUpdate(BaseModel):
    """Schéma pour la mise à jour partielle via PUT/PATCH.
    Tous les champs sont optionnels pour ne modifier que ce qui est transmis.
    """

    intitule: str | None = Field(None, min_length=1, max_length=255)
    departement: str | None = Field(None, max_length=255)
    date_limite: datetime | None = None
    nombre_postes: int | None = Field(None, ge=1, le=1000)
    localisation: str | None = Field(None, max_length=255)
    competences: list[str] | None = None
    experience_requise: str | None = Field(None, max_length=100)
    langues: list[str] | None = None
    niveau_etudes: str | None = Field(None, max_length=100)
    type_contrat: TypeContrat | None = None
    salaire_min: int | None = Field(None, ge=0)
    salaire_max: int | None = Field(None, ge=0)
    recruteurs_responsables: list[uuid.UUID] | None = None
    description: str | None = None
    statut: str | None = Field(
        default=None,
        description="Statut de la campagne (active, terminee, annulee)"
    )
    workflow: list[dict[str, Any]] | None = None

    @field_validator('salaire_min', 'salaire_max')
    @classmethod
    def validate_salaire(cls, v: int | None) -> int | None:
        """Valide que le salaire est positif."""
        if v is not None and v < 0:
            raise ValueError('Le salaire doit être positif')
        return v

    @field_validator('salaire_min', 'salaire_max')
    @classmethod
    def validate_salaire_range(cls, v: int | None, info) -> int | None:
        """Valide que le salaire min est inférieur au salaire max."""
        if 'salaire_min' in info.data and 'salaire_max' in info.data:
            min_val = info.data.get('salaire_min')
            max_val = info.data.get('salaire_max')
            if min_val is not None and max_val is not None and min_val > max_val:
                raise ValueError('Le salaire minimum doit être inférieur au maximum')
        return v


class CampagneResponse(CampagneBase):
    """Schéma renvoyé au Frontend lors de la lecture d'une campagne (GET)."""

    id: uuid.UUID = Field(description="Identifiant unique de la campagne")
    entreprise_id: uuid.UUID = Field(description="ID de l'entreprise propriétaire")
    statut: str = Field(
        default="active",
        description="Statut de la campagne"
    )
    created_at: datetime = Field(description="Date de création")
    updated_at: datetime = Field(description="Date de dernière modification")

    # Propriétés calculées
    nombre_offres: int = Field(
        default=0,
        description="Nombre d'offres associées à la campagne"
    )
    est_terminee: bool = Field(
        default=False,
        description="Indique si la campagne est terminée"
    )
    nombre_postes_pourvus: int = Field(
        default=0,
        description="Nombre de postes pourvus"
    )

    model_config = ConfigDict(from_attributes=True)
