"""Endpoints Abonnements (Lot 1/S4 — Azaël).

Abonnement en libre-service au niveau du tenant : consultation par tout membre,
changement de plan réservé à l'admin RH. Changement **simulé** (pas de paiement).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.enums import RoleUtilisateur, StatutAbonnement
from app.core.plans import PLAN_CATALOG
from app.core.responses import success
from app.models.abonnement import Abonnement
from app.models.utilisateur import Utilisateur
from app.schemas.abonnement import (
    AbonnementResponse,
    ChangePlanRequest,
    PlanCatalogItem,
)

router = APIRouter(prefix="/abonnements", tags=["abonnements"])


@router.get("/plans")
def catalogue_plans(_: Utilisateur = Depends(get_current_user)):
    """Catalogue des plans (libellés, prix, fonctionnalités)."""
    items = [
        PlanCatalogItem(plan=plan, **details)
        for plan, details in PLAN_CATALOG.items()
    ]
    return success(items)


@router.get("/me")
def mon_abonnement(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    abonnement = (
        db.query(Abonnement)
        .filter(Abonnement.entreprise_id == user.entreprise_id)
        .first()
    )
    if abonnement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun abonnement.")
    return success(AbonnementResponse.model_validate(abonnement))


@router.put("/me")
def changer_plan(
    payload: ChangePlanRequest,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in (RoleUtilisateur.admin_rh, RoleUtilisateur.admin_plateforme):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Réservé à l'admin RH de l'entreprise."
        )
    abonnement = (
        db.query(Abonnement)
        .filter(Abonnement.entreprise_id == user.entreprise_id)
        .first()
    )
    if abonnement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun abonnement.")
    # Changement simulé : on bascule le plan et on active l'abonnement.
    abonnement.plan = payload.plan
    abonnement.statut = StatutAbonnement.actif
    db.commit()
    db.refresh(abonnement)
    return success(
        AbonnementResponse.model_validate(abonnement),
        "Plan mis à jour (simulation, sans paiement).",
    )
