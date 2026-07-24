"""Schémas d'entrée/sortie de l'authentification.

Le formulaire d'inscription du frontend gère deux profils : `candidat` et
`recruteur`. Pour un recruteur, le nom d'entreprise détermine le rôle côté
serveur (entreprise nouvelle → admin_rh ; entreprise existante → recruteur).
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.enums import RoleUtilisateur
from app.core.validators import validate_email_domain


class RegisterRequest(BaseModel):
    """Requête d'inscription pour un nouveau compte."""

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
    profil: Literal["candidat", "recruteur"] = Field(
        description="Type de profil : candidat ou recruteur"
    )
    nom_entreprise: str | None = Field(
        default=None,
        max_length=100,
        description="Nom de l'entreprise (requis pour les recruteurs)"
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Valide le domaine de l'email (bloque les emails jetables)."""
        return validate_email_domain(v)

    @field_validator('nom_entreprise')
    @classmethod
    def validate_nom_entreprise(cls, v: str | None) -> str | None:
        """Valide le nom d'entreprise pour les recruteurs."""
        if v is not None and len(v.strip()) < 2:
            raise ValueError("Le nom d'entreprise doit contenir au moins 2 caractères")
        return v.strip() if v else v


class LoginRequest(BaseModel):
    """Requête de connexion."""

    email: EmailStr = Field(
        description="Adresse email de l'utilisateur"
    )
    mot_de_passe: str = Field(
        min_length=1,
        description="Mot de passe de l'utilisateur"
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Valide le domaine de l'email."""
        return validate_email_domain(v)


class VerifyEmailRequest(BaseModel):
    """Requête de vérification d'email."""

    token: str = Field(
        description="Jeton de vérification reçu par email"
    )


class ResendVerificationRequest(BaseModel):
    """Requête pour renvoyer un email de vérification."""

    email: EmailStr = Field(
        description="Adresse email à vérifier"
    )


class IdentityResponse(BaseModel):
    """Identité de session renvoyée par /auth/register, /auth/login, /auth/me."""

    id: str = Field(
        description="Identifiant unique de l'utilisateur"
    )
    type: Literal["utilisateur", "candidat"] = Field(
        description="Type de compte : utilisateur (interne) ou candidat"
    )
    nom: str = Field(
        description="Nom complet de l'utilisateur"
    )
    email: EmailStr = Field(
        description="Adresse email de l'utilisateur"
    )
    role: RoleUtilisateur | None = Field(
        default=None,
        description="Rôle de l'utilisateur (uniquement pour les comptes internes)"
    )
    entreprise_id: str | None = Field(
        default=None,
        description="ID de l'entreprise (uniquement pour les comptes internes)"
    )
    email_verifie: bool = Field(
        default=False,
        description="Indique si l'email a été vérifié"
    )
    actif: bool = Field(
        default=True,
        description="Indique si le compte est actif"
    )
