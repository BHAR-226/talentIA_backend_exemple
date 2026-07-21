"""Endpoints du dashboard admin (Lot 1/S4 — Azaël).

Statistiques réelles du tenant courant : équipe, volume de recrutement, statut
d'abonnement. Réservé aux administrateurs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.enums import RoleUtilisateur
from app.core.responses import success
from app.models.abonnement import Abonnement
from app.models.campagne import Campagne
from app.models.candidature import Candidature
from app.models.offre import Offre
from app.models.utilisateur import Utilisateur
from app.schemas.abonnement import AdminStats

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def stats_admin(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in (RoleUtilisateur.admin_rh, RoleUtilisateur.admin_plateforme):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs.")

    ent_id = user.entreprise_id
    users = (
        db.query(Utilisateur).filter(Utilisateur.entreprise_id == ent_id).all()
    )
    offres_total = (
        db.query(Offre)
        .join(Campagne, Offre.campagne_id == Campagne.id)
        .filter(Campagne.entreprise_id == ent_id)
        .count()
    )
    candidatures_total = (
        db.query(Candidature)
        .join(Offre, Candidature.offre_id == Offre.id)
        .join(Campagne, Offre.campagne_id == Campagne.id)
        .filter(Campagne.entreprise_id == ent_id)
        .count()
    )
    abonnement = (
        db.query(Abonnement).filter(Abonnement.entreprise_id == ent_id).first()
    )

    stats = AdminStats(
        utilisateurs_actifs=sum(1 for u in users if u.actif),
        recruteurs=sum(1 for u in users if u.role == RoleUtilisateur.recruteur),
        offres_total=offres_total,
        candidatures_total=candidatures_total,
        plan=abonnement.plan if abonnement else None,
        statut_abonnement=abonnement.statut if abonnement else None,
    )
    return success(stats)
