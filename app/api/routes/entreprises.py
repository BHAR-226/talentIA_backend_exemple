"""CRUD Entreprises (Lot 1 — Azaël).

Deux niveaux d'accès (cf. cahier des charges) :
  - **admin_plateforme** : voit et gère TOUTES les entreprises (super-admin).
  - **utilisateur d'une entreprise** : accède à SA propre entreprise ; seul un
    **admin_rh** peut l'éditer.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.enums import RoleUtilisateur, StatutEntreprise
from app.core.responses import success
from app.models.entreprise import Entreprise
from app.models.utilisateur import Utilisateur
from app.schemas.entreprise import (
    EntrepriseCreate,
    EntrepriseResponse,
    EntrepriseUpdate,
    SuspendreEntrepriseRequest,
)

router = APIRouter(prefix="/entreprises", tags=["entreprises"])


# ==========================================================
# Fonctions utilitaires
# ==========================================================

def _get_or_404(db: Session, entreprise_id: uuid.UUID) -> Entreprise:
    """Récupère une entreprise ou lève une 404."""
    entreprise = db.get(Entreprise, entreprise_id)
    if entreprise is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entreprise introuvable."
        )
    return entreprise


def _ensure_read(user: Utilisateur, entreprise_id: uuid.UUID) -> None:
    """Vérifie que l'utilisateur a le droit de lire l'entreprise."""
    if user.role == RoleUtilisateur.admin_plateforme:
        return
    if user.entreprise_id == entreprise_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Accès refusé à cette entreprise."
    )


def _ensure_write(user: Utilisateur, entreprise_id: uuid.UUID) -> None:
    """Vérifie que l'utilisateur a le droit de modifier l'entreprise."""
    if user.role == RoleUtilisateur.admin_plateforme:
        return
    if user.role == RoleUtilisateur.admin_rh and user.entreprise_id == entreprise_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Réservé à l'admin RH de l'entreprise."
    )


def _ensure_admin_plateforme(user: Utilisateur) -> None:
    """Vérifie que l'utilisateur est admin plateforme."""
    if user.role != RoleUtilisateur.admin_plateforme:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé à l'admin plateforme."
        )


# ==========================================================
# Routes utilisateur (mon entreprise)
# ==========================================================

@router.get("/me")
def get_mon_entreprise(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Récupère l'entreprise (tenant) de l'utilisateur connecté.

    **Accessible à tous les utilisateurs internes.**
    """
    if not user.entreprise_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="L'utilisateur n'est rattaché à aucune entreprise."
        )

    entreprise = _get_or_404(db, user.entreprise_id)
    return success(EntrepriseResponse.model_validate(entreprise))


@router.get("/me/stats")
def get_mon_entreprise_stats(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Récupère les statistiques de l'entreprise de l'utilisateur connecté.

    **Accessible à tous les utilisateurs internes.**
    """
    if not user.entreprise_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="L'utilisateur n'est rattaché à aucune entreprise."
        )

    entreprise = _get_or_404(db, user.entreprise_id)

    stats = {
        "id": str(entreprise.id),
        "nom": entreprise.nom,
        "statut": entreprise.statut.value,
        "nombre_utilisateurs": entreprise.nombre_utilisateurs,
        "nombre_utilisateurs_actifs": entreprise.nombre_utilisateurs_actifs,
        "nombre_campagnes": entreprise.nombre_campagnes,
        "nombre_campagnes_actives": entreprise.nombre_campagnes_actives,
        "a_abonnement_actif": entreprise.a_abonnement_actif,
    }

    return success(stats)


# ==========================================================
# Routes admin plateforme
# ==========================================================

@router.get("")
def lister_entreprises(
    user: Utilisateur = Depends(get_current_user),
    statut: str | None = Query(None, description="Filtrer par statut"),
    search: str | None = Query(None, description="Rechercher par nom"),
    db: Session = Depends(get_db),
):
    """Liste toutes les entreprises (réservé à l'admin plateforme).

    **Filtres disponibles :**
    - `statut` : Filtrer par statut (active, suspendue)
    - `search` : Recherche textuelle dans le nom
    """
    _ensure_admin_plateforme(user)

    query = db.query(Entreprise)

    if statut:
        query = query.filter(Entreprise.statut == statut)

    if search:
        query = query.filter(Entreprise.nom.ilike(f"%{search}%"))

    entreprises = query.order_by(Entreprise.nom).all()
    return success([EntrepriseResponse.model_validate(e) for e in entreprises])


@router.post("", status_code=status.HTTP_201_CREATED)
def creer_entreprise(
    payload: EntrepriseCreate,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crée une nouvelle entreprise (réservé à l'admin plateforme).
    """
    _ensure_admin_plateforme(user)

    entreprise = Entreprise(**payload.model_dump())
    db.add(entreprise)
    db.commit()
    db.refresh(entreprise)

    return success(
        EntrepriseResponse.model_validate(entreprise),
        "Entreprise créée avec succès."
    )


# ==========================================================
# Routes CRUD par ID
# ==========================================================

@router.get("/{entreprise_id}")
def get_entreprise(
    entreprise_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Récupère une entreprise par son ID.

    **Permissions :**
    - Admin plateforme : toutes les entreprises
    - Autres utilisateurs : seulement leur entreprise
    """
    _ensure_read(user, entreprise_id)
    entreprise = _get_or_404(db, entreprise_id)
    return success(EntrepriseResponse.model_validate(entreprise))


@router.put("/{entreprise_id}")
def update_entreprise(
    entreprise_id: uuid.UUID,
    payload: EntrepriseUpdate,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Met à jour une entreprise.

    **Permissions :**
    - Admin plateforme : toutes les entreprises
    - Admin RH : seulement son entreprise
    """
    _ensure_write(user, entreprise_id)
    entreprise = _get_or_404(db, entreprise_id)

    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(entreprise, champ, valeur)

    db.commit()
    db.refresh(entreprise)

    return success(
        EntrepriseResponse.model_validate(entreprise),
        "Entreprise mise à jour avec succès."
    )


# ==========================================================
# Routes de suspension
# ==========================================================

@router.put("/{entreprise_id}/suspendre")
def suspendre_entreprise(
    entreprise_id: uuid.UUID,
    payload: SuspendreEntrepriseRequest,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Suspend une entreprise (réservé à l'admin plateforme).

    Coupe l'accès de TOUS les membres de l'entreprise dès la requête suivante.
    Réversible via `/reactiver`.
    """
    _ensure_admin_plateforme(user)

    if entreprise_id == user.entreprise_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de suspendre votre propre entreprise (plateforme)."
        )

    entreprise = _get_or_404(db, entreprise_id)
    entreprise.suspendre(payload.motif)
    db.commit()
    db.refresh(entreprise)

    return success(
        EntrepriseResponse.model_validate(entreprise),
        "Entreprise suspendue avec succès."
    )


@router.put("/{entreprise_id}/reactiver")
def reactiver_entreprise(
    entreprise_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Réactive une entreprise suspendue (réservé à l'admin plateforme).
    """
    _ensure_admin_plateforme(user)

    entreprise = _get_or_404(db, entreprise_id)
    entreprise.reactiver()
    db.commit()
    db.refresh(entreprise)

    return success(
        EntrepriseResponse.model_validate(entreprise),
        "Entreprise réactivée avec succès."
    )


# ==========================================================
# Route de statistiques (admin plateforme)
# ==========================================================

@router.get("/stats/global")
def stats_globales(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Statistiques globales de toutes les entreprises (réservé à l'admin plateforme).
    """
    _ensure_admin_plateforme(user)

    total_entreprises = db.query(Entreprise).count()
    entreprises_actives = db.query(Entreprise).filter(
        Entreprise.statut == StatutEntreprise.active
    ).count()
    entreprises_suspendues = db.query(Entreprise).filter(
        Entreprise.statut == StatutEntreprise.suspendue
    ).count()

    stats = {
        "total_entreprises": total_entreprises,
        "entreprises_actives": entreprises_actives,
        "entreprises_suspendues": entreprises_suspendues,
        "taux_activation": round((entreprises_actives / total_entreprises) * 100, 2) if total_entreprises > 0 else 0,
    }

    return success(stats)
