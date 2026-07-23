"""Endpoints Abonnements (Lot 1/S4 — Azaël).

Abonnement en libre-service au niveau du tenant : consultation par tout membre,
changement de plan réservé à l'admin RH. Changement **simulé** (pas de paiement).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.cache import cache
from app.core.database import get_db
from app.core.enums import PlanAbonnement, RoleUtilisateur, StatutAbonnement
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
    """Récupère l'abonnement de l'entreprise connectée."""
    abonnement = (
        db.query(Abonnement)
        .filter(Abonnement.entreprise_id == user.entreprise_id)
        .first()
    )
    if abonnement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun abonnement trouvé pour cette entreprise."
        )
    
    # Ajouter les propriétés calculées
    response = AbonnementResponse.model_validate(abonnement)
    return success(response)


@router.put("/me")
async def changer_plan(
    payload: ChangePlanRequest,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change le plan d'abonnement (simulation, sans paiement).
    
    Réservé à l'admin RH ou admin plateforme.
    """
    # Vérifier les permissions
    if user.role not in (RoleUtilisateur.admin_rh, RoleUtilisateur.admin_plateforme):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé à l'admin RH de l'entreprise."
        )
    
    # Récupérer l'abonnement
    abonnement = (
        db.query(Abonnement)
        .filter(Abonnement.entreprise_id == user.entreprise_id)
        .first()
    )
    if abonnement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun abonnement trouvé pour cette entreprise."
        )
    
    # Vérifier que le plan existe dans le catalogue
    if payload.plan not in PLAN_CATALOG:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan '{payload.plan}' non disponible."
        )
    
    # Changement simulé
    ancien_plan = abonnement.plan
    abonnement.plan = payload.plan
    abonnement.statut = StatutAbonnement.actif
    
    # Si le plan est enterprise, on active le renouvellement auto par défaut
    if payload.plan == PlanAbonnement.enterprise:
        abonnement.renouvellement_auto = True
    
    db.commit()
    db.refresh(abonnement)
    
    # Invalider le cache des stats
    cache_key = f"admin_stats:{user.entreprise_id}"
    await cache.delete(cache_key)
    
    return success(
        AbonnementResponse.model_validate(abonnement),
        f"Plan mis à jour : {ancien_plan.value} → {payload.plan.value} (simulation, sans paiement)."
    )


@router.get("/historique")
def historique_abonnement(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Récupère l'historique des abonnements (à implémenter avec un modèle d'historique)."""
    # TODO: Ajouter un modèle HistoriqueAbonnement pour suivre les changements
    return success({
        "message": "L'historique des abonnements sera disponible prochainement.",
        "current_plan": None
    })