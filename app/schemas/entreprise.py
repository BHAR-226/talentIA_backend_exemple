"""Schémas de l'entité Entreprise (profil du tenant)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import StatutEntreprise


class EntrepriseCreate(BaseModel):
    """Schéma pour la création d'une entreprise."""

    nom: str = Field(
        min_length=2,
        max_length=100,
        description="Nom de l'entreprise"
    )
    domaine: str | None = Field(
        default=None,
        max_length=100,
        description="Domaine d'activité"
    )
    secteur: str | None = Field(
        default=None,
        max_length=100,
        description="Secteur d'activité"
    )
    taille: str | None = Field(
        default=None,
        max_length=50,
        description="Taille de l'entreprise (ex: PME, Grand Groupe)"
    )
    adresse: str | None = Field(
        default=None,
        max_length=500,
        description="Adresse de l'entreprise"
    )
    logo_url: str | None = Field(
        default=None,
        max_length=500,
        description="URL du logo"
    )
    site_web: str | None = Field(
        default=None,
        max_length=255,
        description="Site web de l'entreprise"
    )
    telephone: str | None = Field(
        default=None,
        max_length=50,
        description="Numéro de téléphone"
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Description de l'entreprise"
    )

    @field_validator('nom')
    @classmethod
    def validate_nom(cls, v: str) -> str:
        """Valide et formate le nom de l'entreprise."""
        if not v or not v.strip():
            raise ValueError('Le nom ne peut pas être vide')
        return v.strip().title()


class EntrepriseUpdate(BaseModel):
    """Schéma pour la mise à jour partielle d'une entreprise.
    Tous les champs sont optionnels (PATCH-like).
    """

    nom: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Nom de l'entreprise"
    )
    domaine: str | None = Field(
        default=None,
        max_length=100,
        description="Domaine d'activité"
    )
    secteur: str | None = Field(
        default=None,
        max_length=100,
        description="Secteur d'activité"
    )
    taille: str | None = Field(
        default=None,
        max_length=50,
        description="Taille de l'entreprise"
    )
    adresse: str | None = Field(
        default=None,
        max_length=500,
        description="Adresse de l'entreprise"
    )
    logo_url: str | None = Field(
        default=None,
        max_length=500,
        description="URL du logo"
    )
    site_web: str | None = Field(
        default=None,
        max_length=255,
        description="Site web de l'entreprise"
    )
    telephone: str | None = Field(
        default=None,
        max_length=50,
        description="Numéro de téléphone"
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Description de l'entreprise"
    )

    @field_validator('nom')
    @classmethod
    def validate_nom(cls, v: str | None) -> str | None:
        """Valide et formate le nom de l'entreprise."""
        if v is not None:
            if not v.strip():
                raise ValueError('Le nom ne peut pas être vide')
            return v.strip().title()
        return v


class SuspendreEntrepriseRequest(BaseModel):
    """Requête pour suspendre une entreprise."""

    motif: str = Field(
        min_length=1,
        max_length=500,
        description="Motif de la suspension"
    )


class EntrepriseResponse(BaseModel):
    """Réponse complète d'une entreprise."""

    model_config = ConfigDict(from_attributes=True)

    # Identifiants
    id: uuid.UUID = Field(description="ID unique de l'entreprise")

    # Informations générales
    nom: str = Field(description="Nom de l'entreprise")
    domaine: str | None = Field(default=None, description="Domaine d'activité")
    secteur: str | None = Field(default=None, description="Secteur d'activité")
    taille: str | None = Field(default=None, description="Taille de l'entreprise")
    adresse: str | None = Field(default=None, description="Adresse de l'entreprise")
    logo_url: str | None = Field(default=None, description="URL du logo")

    # Contact
    site_web: str | None = Field(default=None, description="Site web de l'entreprise")
    telephone: str | None = Field(default=None, description="Numéro de téléphone")
    description: str | None = Field(default=None, description="Description de l'entreprise")

    # Statut
    statut: StatutEntreprise = Field(
        default=StatutEntreprise.active,
        description="Statut de l'entreprise"
    )
    motif_suspension: str | None = Field(
        default=None,
        description="Motif de la suspension (si applicable)"
    )

    # Métadonnées
    created_at: datetime = Field(description="Date de création")
    updated_at: datetime = Field(description="Date de dernière modification")

    @property
    def est_active(self) -> bool:
        """Vérifie si l'entreprise est active."""
        return self.statut == StatutEntreprise.active

    @property
    def est_suspendue(self) -> bool:
        """Vérifie si l'entreprise est suspendue."""
        return self.statut == StatutEntreprise.suspendue
