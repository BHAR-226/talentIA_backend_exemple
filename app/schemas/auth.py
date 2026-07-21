"""Schémas d'entrée/sortie de l'authentification.

Le formulaire d'inscription du frontend gère deux profils : `candidat` et
`recruteur`. Pour un recruteur, le nom d'entreprise détermine le rôle côté
serveur (entreprise nouvelle → admin_rh ; entreprise existante → recruteur).
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import RoleUtilisateur


class RegisterRequest(BaseModel):
    nom: str = Field(min_length=1)
    email: EmailStr
    mot_de_passe: str = Field(min_length=4)
    profil: Literal["candidat", "recruteur"]
    nom_entreprise: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    mot_de_passe: str


class IdentityResponse(BaseModel):
    """Identité de session renvoyée par /auth/register, /auth/login, /auth/me."""

    id: str
    type: Literal["utilisateur", "candidat"]
    nom: str
    email: EmailStr
    role: RoleUtilisateur | None = None
    entreprise_id: str | None = None
