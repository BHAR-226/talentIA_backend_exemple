"""Schémas de l'entité Candidat (profil, hors flux d'inscription/auth)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.validators import validate_phone


class CandidatProfilUpdate(BaseModel):
    """Schéma pour la mise à jour du profil candidat.
    Tous les champs sont optionnels pour une mise à jour partielle.
    """

    nom: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nom complet du candidat"
    )
    telephone: str | None = Field(
        default=None,
        max_length=50,
        description="Numéro de téléphone"
    )
    titre_principal: str | None = Field(
        default=None,
        max_length=255,
        description="Titre ou poste actuel"
    )
    annees_experience: int | None = Field(
        default=None,
        ge=0,
        le=60,
        description="Nombre d'années d'expérience"
    )
    localisation: str | None = Field(
        default=None,
        max_length=255,
        description="Localisation géographique"
    )
    linkedin_url: str | None = Field(
        default=None,
        max_length=255,
        description="URL du profil LinkedIn"
    )
    portfolio_url: str | None = Field(
        default=None,
        max_length=255,
        description="URL du portfolio"
    )
    disponibilite: str | None = Field(
        default=None,
        max_length=50,
        description="Disponibilité (immediate, 1 mois, etc.)"
    )
    preavis: int | None = Field(
        default=None,
        ge=0,
        le=365,
        description="Durée du préavis en jours"
    )
    pret_a_relocaliser: bool | None = Field(
        default=None,
        description="Prêt à se relocaliser"
    )
    permis_conduire: bool | None = Field(
        default=None,
        description="Possède un permis de conduire"
    )

    @field_validator('telephone')
    @classmethod
    def validate_telephone(cls, v: str | None) -> str | None:
        """Valide le format du numéro de téléphone."""
        if v:
            return validate_phone(v)
        return v


class ChangerMotDePasseCandidatRequest(BaseModel):
    """Schéma pour le changement de mot de passe du candidat."""

    mot_de_passe_actuel: str = Field(
        description="Mot de passe actuel"
    )
    nouveau_mot_de_passe: str = Field(
        min_length=4,
        max_length=100,
        description="Nouveau mot de passe (minimum 4 caractères)"
    )


class CandidatResponse(BaseModel):
    """Réponse complète d'un candidat."""

    model_config = ConfigDict(from_attributes=True)

    # Identifiants
    id: uuid.UUID = Field(description="ID unique du candidat")

    # Informations personnelles
    nom: str = Field(description="Nom complet du candidat")
    email: EmailStr = Field(description="Adresse email")
    telephone: str | None = Field(
        default=None,
        description="Numéro de téléphone"
    )

    # Profil professionnel
    titre_principal: str | None = Field(
        default=None,
        description="Titre ou poste actuel"
    )
    annees_experience: int | None = Field(
        default=None,
        description="Nombre d'années d'expérience"
    )
    localisation: str | None = Field(
        default=None,
        description="Localisation géographique"
    )

    # CV
    cv_url: str | None = Field(
        default=None,
        description="URL du CV uploadé"
    )
    a_upload_cv: bool = Field(
        default=False,
        description="Indique si le candidat a uploadé un CV"
    )

    # Réseaux et portfolio
    linkedin_url: str | None = Field(
        default=None,
        description="URL du profil LinkedIn"
    )
    portfolio_url: str | None = Field(
        default=None,
        description="URL du portfolio"
    )

    # Disponibilité
    disponibilite: str | None = Field(
        default=None,
        description="Disponibilité du candidat"
    )
    preavis: int | None = Field(
        default=None,
        description="Durée du préavis en jours"
    )
    pret_a_relocaliser: bool = Field(
        default=False,
        description="Prêt à se relocaliser"
    )
    permis_conduire: bool = Field(
        default=False,
        description="Possède un permis de conduire"
    )

    # Statut du compte
    email_verifie: bool = Field(
        default=False,
        description="Email vérifié"
    )

    # Métadonnées
    created_at: datetime = Field(description="Date de création du compte")
    updated_at: datetime = Field(description="Date de dernière mise à jour")

    # Métriques calculées
    nombre_candidatures: int = Field(
        default=0,
        description="Nombre total de candidatures soumises"
    )
