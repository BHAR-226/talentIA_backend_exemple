"""Schémas de l'entité Entreprise (profil du tenant)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EntrepriseCreate(BaseModel):
    nom: str
    domaine: str | None = None
    secteur: str | None = None
    taille: str | None = None
    adresse: str | None = None
    logo_url: str | None = None


class EntrepriseUpdate(BaseModel):
    """Tous les champs optionnels : édition partielle (PATCH-like)."""

    nom: str | None = None
    domaine: str | None = None
    secteur: str | None = None
    taille: str | None = None
    adresse: str | None = None
    logo_url: str | None = None


class EntrepriseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom: str
    domaine: str | None
    secteur: str | None
    taille: str | None
    adresse: str | None
    logo_url: str | None
    created_at: datetime
