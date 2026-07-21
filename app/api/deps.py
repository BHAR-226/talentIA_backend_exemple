"""Dépendances FastAPI partagées : session DB déjà fournie par `get_db`, et
surtout `get_current_user` — le point d'authentification réutilisable par TOUS
les endpoints (lit le cookie httpOnly, valide le JWT, charge l'utilisateur).
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.enums import RoleUtilisateur
from app.core.security import decode_access_token
from app.models.candidat import Candidat
from app.models.utilisateur import Utilisateur


@dataclass
class CurrentIdentity:
    """Identité de la session, quel que soit le type de compte."""

    id: uuid.UUID
    type: str  # "utilisateur" | "candidat"
    nom: str
    role: RoleUtilisateur | None = None
    entreprise_id: uuid.UUID | None = None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def get_current_identity(
    request: Request, db: Session = Depends(get_db)
) -> CurrentIdentity:
    """Résout la session (utilisateur OU candidat) depuis le cookie httpOnly."""
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise _unauthorized("Non authentifié.")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise _unauthorized("Session invalide ou expirée.") from None

    sub, type_compte = payload.get("sub"), payload.get("type")
    if not sub or type_compte not in ("utilisateur", "candidat"):
        raise _unauthorized("Session invalide.")

    if type_compte == "utilisateur":
        user = db.get(Utilisateur, uuid.UUID(sub))
        if user is None or not user.actif:
            raise _unauthorized("Compte introuvable ou désactivé.")
        return CurrentIdentity(
            id=user.id,
            type="utilisateur",
            nom=user.nom,
            role=user.role,
            entreprise_id=user.entreprise_id,
        )

    candidat = db.get(Candidat, uuid.UUID(sub))
    if candidat is None:
        raise _unauthorized("Compte introuvable.")
    return CurrentIdentity(id=candidat.id, type="candidat", nom=candidat.nom)


def get_current_user(
    db: Session = Depends(get_db),
    identity: CurrentIdentity = Depends(get_current_identity),
) -> Utilisateur:
    """Utilisateur interne courant. Refuse les comptes candidat (403)."""
    if identity.type != "utilisateur":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé aux comptes internes de l'entreprise.",
        )
    user = db.get(Utilisateur, identity.id)
    if user is None or not user.actif:
        raise _unauthorized("Compte introuvable ou désactivé.")
    return user


def require_roles(*roles: RoleUtilisateur) -> Callable[..., Utilisateur]:
    """Garde d'accès par rôle (RBAC). Ex. `Depends(require_roles(RoleUtilisateur.admin_rh))`."""

    def checker(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé."
            )
        return user

    return checker
