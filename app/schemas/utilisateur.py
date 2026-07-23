"""Schémas de l'entité Utilisateur (comptes internes d'une entreprise)."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import RoleUtilisateur
from app.core.validators import validate_email_domain


class UtilisateurCreate(BaseModel):
    """Schéma pour la création d'un utilisateur par un admin RH."""
    
    nom: str = Field(
        min_length=1,
        max_length=100,
        description="Nom complet de l'utilisateur"
    )
    email: EmailStr = Field(
        description="Adresse email de l'utilisateur"
    )
    mot_de_passe: str = Field(
        min_length=4,
        max_length=100,
        description="Mot de passe (minimum 4 caractères)"
    )
    role: RoleUtilisateur = Field(
        default=RoleUtilisateur.recruteur,
        description="Rôle de l'utilisateur"
    )
    telephone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Numéro de téléphone"
    )
    fonction: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Fonction ou poste occupé"
    )
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Valide le domaine de l'email."""
        return validate_email_domain(v)


class UtilisateurUpdate(BaseModel):
    """Schéma pour la mise à jour d'un utilisateur par un admin RH.
    Tous les champs sont optionnels pour une mise à jour partielle.
    """
    
    nom: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nom complet de l'utilisateur"
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Adresse email de l'utilisateur"
    )
    role: Optional[RoleUtilisateur] = Field(
        default=None,
        description="Rôle de l'utilisateur"
    )
    actif: Optional[bool] = Field(
        default=None,
        description="Indique si le compte est actif"
    )
    telephone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Numéro de téléphone"
    )
    fonction: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Fonction ou poste occupé"
    )
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Valide le domaine de l'email."""
        if v:
            return validate_email_domain(v)
        return v


class ProfilUtilisateurUpdate(BaseModel):
    """Schéma pour la mise à jour du profil personnel d'un utilisateur.
    L'utilisateur peut modifier son nom, email, téléphone et fonction.
    """
    
    nom: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nom complet de l'utilisateur"
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Adresse email de l'utilisateur"
    )
    telephone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Numéro de téléphone"
    )
    fonction: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Fonction ou poste occupé"
    )
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Valide le domaine de l'email."""
        if v:
            return validate_email_domain(v)
        return v


class ChangerMotDePasseRequest(BaseModel):
    """Schéma pour le changement de mot de passe d'un utilisateur."""
    
    mot_de_passe_actuel: str = Field(
        description="Mot de passe actuel de l'utilisateur"
    )
    nouveau_mot_de_passe: str = Field(
        min_length=4,
        max_length=100,
        description="Nouveau mot de passe (minimum 4 caractères)"
    )


class UtilisateurResponse(BaseModel):
    """Réponse complète d'un utilisateur."""
    
    model_config = ConfigDict(from_attributes=True)
    
    # Identifiants
    id: uuid.UUID = Field(description="ID unique de l'utilisateur")
    entreprise_id: uuid.UUID = Field(description="ID de l'entreprise associée")
    
    # Informations personnelles
    nom: str = Field(description="Nom complet de l'utilisateur")
    email: str = Field(description="Adresse email")
    telephone: Optional[str] = Field(
        default=None,
        description="Numéro de téléphone"
    )
    fonction: Optional[str] = Field(
        default=None,
        description="Fonction ou poste occupé"
    )
    
    # Rôle et statut
    role: RoleUtilisateur = Field(description="Rôle de l'utilisateur")
    actif: bool = Field(
        default=True,
        description="Indique si le compte est actif"
    )
    email_verifie: bool = Field(
        default=False,
        description="Indique si l'email a été vérifié"
    )
    
    # Métadonnées
    created_at: datetime = Field(description="Date de création du compte")
    updated_at: datetime = Field(description="Date de dernière mise à jour")
    derniere_connexion: Optional[datetime] = Field(
        default=None,
        description="Date de dernière connexion"
    )