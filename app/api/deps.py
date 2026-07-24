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
from app.core.enums import RoleUtilisateur, StatutEntreprise
from app.core.security import decode_access_token
from app.models.candidat import Candidat
from app.models.utilisateur import Utilisateur


@dataclass
class CurrentIdentity:
    """Identité de la session, quel que soit le type de compte.

    Attributes:
        id: Identifiant unique de l'utilisateur ou du candidat
        type: "utilisateur" ou "candidat"
        nom: Nom complet
        role: Rôle (uniquement pour les utilisateurs internes)
        entreprise_id: ID de l'entreprise (uniquement pour les utilisateurs internes)
    """

    id: uuid.UUID
    type: str  # "utilisateur" | "candidat"
    nom: str
    role: RoleUtilisateur | None = None
    entreprise_id: uuid.UUID | None = None

    @property
    def est_utilisateur(self) -> bool:
        """Indique si l'identité est un utilisateur interne."""
        return self.type == "utilisateur"

    @property
    def est_candidat(self) -> bool:
        """Indique si l'identité est un candidat."""
        return self.type == "candidat"


def _unauthorized(detail: str) -> HTTPException:
    """Lève une exception 401 Non authentifié."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str) -> HTTPException:
    """Lève une exception 403 Accès refusé."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


# ==========================================================
# Dépendance principale d'authentification
# ==========================================================

def get_current_identity(
    request: Request,
    db: Session = Depends(get_db)
) -> CurrentIdentity:
    """Résout la session (utilisateur OU candidat) depuis le cookie httpOnly.

    Vérifie à chaque requête (pas seulement à la connexion) que le compte est
    toujours valide :
    - Email confirmé
    - Compte actif
    - Pour un utilisateur interne : entreprise non suspendue

    Un token émis avant une suspension ou une désactivation est ainsi
    immédiatement invalidé.
    """
    # 1. Récupérer le token depuis le cookie
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise _unauthorized("Non authentifié.")

    # 2. Décoder et valider le JWT
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise _unauthorized("Session invalide ou expirée.") from None

    sub = payload.get("sub")
    type_compte = payload.get("type")

    if not sub or type_compte not in ("utilisateur", "candidat"):
        raise _unauthorized("Session invalide.")

    # 3. Charger et valider l'utilisateur
    if type_compte == "utilisateur":
        return _validate_utilisateur(db, uuid.UUID(sub))

    # 4. Charger et valider le candidat
    return _validate_candidat(db, uuid.UUID(sub))


def _validate_utilisateur(db: Session, user_id: uuid.UUID) -> CurrentIdentity:
    """Valide un utilisateur interne."""
    user = db.get(Utilisateur, user_id)

    if user is None:
        raise _unauthorized("Compte introuvable.")

    if user.is_deleted:
        raise _unauthorized("Compte supprimé.")

    if not user.email_verifie:
        raise _forbidden("Email non confirmé.")

    if not user.actif:
        raise _forbidden("Compte désactivé ou en attente de validation.")

    if user.entreprise.statut == StatutEntreprise.suspendue:
        raise _forbidden("Entreprise suspendue.")

    return CurrentIdentity(
        id=user.id,
        type="utilisateur",
        nom=user.nom,
        role=user.role,
        entreprise_id=user.entreprise_id,
    )


def _validate_candidat(db: Session, candidat_id: uuid.UUID) -> CurrentIdentity:
    """Valide un candidat."""
    candidat = db.get(Candidat, candidat_id)

    if candidat is None:
        raise _unauthorized("Compte introuvable.")

    if candidat.is_deleted:
        raise _unauthorized("Compte supprimé.")

    if not candidat.email_verifie:
        raise _forbidden("Email non confirmé.")

    return CurrentIdentity(
        id=candidat.id,
        type="candidat",
        nom=candidat.nom,
    )


# ==========================================================
# Dépendances spécifiques
# ==========================================================

def get_current_user(
    db: Session = Depends(get_db),
    identity: CurrentIdentity = Depends(get_current_identity),
) -> Utilisateur:
    """Utilisateur interne courant. Refuse les comptes candidat (403).

    Returns:
        Utilisateur: L'utilisateur interne authentifié.

    Raises:
        HTTPException: 403 si le compte est un candidat.
        HTTPException: 401 si l'utilisateur n'est pas trouvé ou désactivé.
    """
    if identity.type != "utilisateur":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé aux comptes internes de l'entreprise.",
        )

    user = db.get(Utilisateur, identity.id)
    if user is None or not user.actif or user.is_deleted:
        raise _unauthorized("Compte introuvable ou désactivé.")

    return user


def get_current_candidat(
    db: Session = Depends(get_db),
    identity: CurrentIdentity = Depends(get_current_identity),
) -> Candidat:
    """Candidat courant. Refuse les comptes internes (403).

    Symétrique de `get_current_user`.

    Returns:
        Candidat: Le candidat authentifié.

    Raises:
        HTTPException: 403 si le compte est un utilisateur interne.
        HTTPException: 401 si le candidat n'est pas trouvé.
    """
    if identity.type != "candidat":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé aux comptes candidat.",
        )

    candidat = db.get(Candidat, identity.id)
    if candidat is None or candidat.is_deleted:
        raise _unauthorized("Compte introuvable.")

    return candidat


def get_current_user_or_candidat(
    identity: CurrentIdentity = Depends(get_current_identity),
) -> CurrentIdentity:
    """Retourne l'identité courante (utilisateur ou candidat).

    Utile pour les endpoints accessibles aux deux types de comptes.
    """
    return identity


# ==========================================================
# RBAC - Role-Based Access Control
# ==========================================================

def require_roles(*roles: RoleUtilisateur) -> Callable[..., Utilisateur]:
    """Garde d'accès par rôle (RBAC).

    Exemple:
        @router.get("/admin")
        def admin_route(
            user: Utilisateur = Depends(require_roles(RoleUtilisateur.admin_rh))
        ):
            ...

    Args:
        *roles: Liste des rôles autorisés à accéder à la route.

    Returns:
        Callable: Dépendance FastAPI qui vérifie le rôle.
    """
    def checker(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôle requis: {', '.join(r.value for r in roles)}"
            )
        return user

    return checker


def require_admin_plateforme() -> Callable[..., Utilisateur]:
    """Garde d'accès spécifique pour l'admin plateforme."""
    return require_roles(RoleUtilisateur.admin_plateforme)


def require_admin_rh() -> Callable[..., Utilisateur]:
    """Garde d'accès spécifique pour l'admin RH."""
    return require_roles(RoleUtilisateur.admin_rh)


def require_recruteur_ou_admin() -> Callable[..., Utilisateur]:
    """Garde d'accès pour les recruteurs et admins."""
    return require_roles(RoleUtilisateur.recruteur, RoleUtilisateur.admin_rh)


# ==========================================================
# Vérification des permissions
# ==========================================================

def check_entreprise_access(user: Utilisateur, entreprise_id: uuid.UUID) -> None:
    """Vérifie que l'utilisateur a accès à l'entreprise donnée.

    Args:
        user: Utilisateur connecté
        entreprise_id: ID de l'entreprise à vérifier

    Raises:
        HTTPException: 403 si l'accès est refusé.
    """
    if user.role != RoleUtilisateur.admin_plateforme and user.entreprise_id != entreprise_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette entreprise."
        )


def check_tenant_access(user: Utilisateur, resource_entreprise_id: uuid.UUID) -> None:
    """Alias pour check_entreprise_access (multi-tenant)."""
    check_entreprise_access(user, resource_entreprise_id)
