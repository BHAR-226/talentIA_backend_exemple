"""CRUD Entreprises (Lot 1 — Azaël).

Deux niveaux d'accès (cf. cahier des charges) :
  - **admin_plateforme** : voit et gère TOUTES les entreprises (super-admin).
  - **utilisateur d'une entreprise** : accède à SA propre entreprise ; seul un
    **admin_rh** peut l'éditer.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.enums import RoleUtilisateur
from app.core.responses import success
from app.models.entreprise import Entreprise
from app.models.utilisateur import Utilisateur
from app.schemas.entreprise import (
    EntrepriseCreate,
    EntrepriseResponse,
    EntrepriseUpdate,
)

router = APIRouter(prefix="/entreprises", tags=["entreprises"])


def _get_or_404(db: Session, entreprise_id: uuid.UUID) -> Entreprise:
    entreprise = db.get(Entreprise, entreprise_id)
    if entreprise is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entreprise introuvable.")
    return entreprise


def _ensure_read(user: Utilisateur, entreprise_id: uuid.UUID) -> None:
    if user.role == RoleUtilisateur.admin_plateforme:
        return
    if user.entreprise_id == entreprise_id:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès refusé.")


def _ensure_write(user: Utilisateur, entreprise_id: uuid.UUID) -> None:
    if user.role == RoleUtilisateur.admin_plateforme:
        return
    if user.role == RoleUtilisateur.admin_rh and user.entreprise_id == entreprise_id:
        return
    raise HTTPException(
        status.HTTP_403_FORBIDDEN, "Réservé à l'admin RH de l'entreprise."
    )


@router.get("/me")
def get_mon_entreprise(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Entreprise (tenant) de l'utilisateur connecté."""
    entreprise = _get_or_404(db, user.entreprise_id)
    return success(EntrepriseResponse.model_validate(entreprise))


@router.get("")
def lister_entreprises(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Liste de toutes les entreprises — réservé à l'admin plateforme."""
    if user.role != RoleUtilisateur.admin_plateforme:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé à l'admin plateforme.")
    entreprises = db.query(Entreprise).order_by(Entreprise.nom).all()
    return success([EntrepriseResponse.model_validate(e) for e in entreprises])


@router.post("", status_code=status.HTTP_201_CREATED)
def creer_entreprise(
    payload: EntrepriseCreate,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Création d'une entreprise — réservé à l'admin plateforme."""
    if user.role != RoleUtilisateur.admin_plateforme:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé à l'admin plateforme.")
    entreprise = Entreprise(**payload.model_dump())
    db.add(entreprise)
    db.commit()
    db.refresh(entreprise)
    return success(EntrepriseResponse.model_validate(entreprise), "Entreprise créée.")


@router.get("/{entreprise_id}")
def get_entreprise(
    entreprise_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    _ensure_write(user, entreprise_id)
    entreprise = _get_or_404(db, entreprise_id)
    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(entreprise, champ, valeur)
    db.commit()
    db.refresh(entreprise)
    return success(EntrepriseResponse.model_validate(entreprise), "Entreprise mise à jour.")
