"""Endpoints du dashboard admin (Lot 1/S4 — Azaël).

Statistiques réelles du tenant courant : équipe, volume de recrutement, statut
d'abonnement. Réservé aux administrateurs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.cache import cache
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
async def stats_admin(
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Récupère les statistiques du tableau de bord admin.
    
    **Données retournées :**
    - Nombre d'utilisateurs actifs
    - Nombre de recruteurs
    - Nombre total d'offres
    - Nombre total de candidatures
    - Nombre de campagnes actives
    - Taux de conversion (candidatures / offres)
    - Plan d'abonnement actuel
    - Statut de l'abonnement
    
    **Permissions :** Admin RH ou Admin Plateforme uniquement.
    """
    # Vérifier les permissions
    if user.role not in (RoleUtilisateur.admin_rh, RoleUtilisateur.admin_plateforme):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé aux administrateurs (Admin RH ou Admin Plateforme)."
        )

    ent_id = user.entreprise_id
    
    # Vérifier le cache
    cache_key = f"admin_stats:{ent_id}"
    cached = await cache.get(cache_key)
    if cached:
        return success(cached)

    # ==========================================================
    # Statistiques des utilisateurs
    # ==========================================================
    
    utilisateurs = (
        db.query(Utilisateur)
        .filter(
            Utilisateur.entreprise_id == ent_id,
            Utilisateur.deleted_at.is_(None)  # Soft delete
        )
        .all()
    )
    
    utilisateurs_actifs = sum(1 for u in utilisateurs if u.actif)
    recruteurs = sum(1 for u in utilisateurs if u.role == RoleUtilisateur.recruteur)
    admins_rh = sum(1 for u in utilisateurs if u.role == RoleUtilisateur.admin_rh)
    evaluateurs = sum(1 for u in utilisateurs if u.role == RoleUtilisateur.evaluateur_technique)
    
    # ==========================================================
    # Statistiques des offres
    # ==========================================================
    
    offres_total = (
        db.query(Offre)
        .join(Campagne, Offre.campagne_id == Campagne.id)
        .filter(Campagne.entreprise_id == ent_id)
        .count()
    )
    
    offres_publiees = (
        db.query(Offre)
        .join(Campagne, Offre.campagne_id == Campagne.id)
        .filter(
            Campagne.entreprise_id == ent_id,
            Offre.statut == "publiee"
        )
        .count()
    )
    
    offres_brouillon = (
        db.query(Offre)
        .join(Campagne, Offre.campagne_id == Campagne.id)
        .filter(
            Campagne.entreprise_id == ent_id,
            Offre.statut == "brouillon"
        )
        .count()
    )
    
    # ==========================================================
    # Statistiques des candidatures
    # ==========================================================
    
    candidatures_total = (
        db.query(Candidature)
        .join(Offre, Candidature.offre_id == Offre.id)
        .join(Campagne, Offre.campagne_id == Campagne.id)
        .filter(Campagne.entreprise_id == ent_id)
        .count()
    )
    
    # Candidatures par statut
    candidatures_par_statut = {}
    for statut in [
        "recue", "en_cours_analyse", "preselectionnee", 
        "test_technique", "entretien_rh", "entretien_metier",
        "verification_references", "decision", "offre_envoyee",
        "embauche", "refusee", "vivier_talents"
    ]:
        count = (
            db.query(Candidature)
            .join(Offre, Candidature.offre_id == Offre.id)
            .join(Campagne, Offre.campagne_id == Campagne.id)
            .filter(
                Campagne.entreprise_id == ent_id,
                Candidature.statut == statut
            )
            .count()
        )
        if count > 0:
            candidatures_par_statut[statut] = count
    
    # ==========================================================
    # Statistiques des campagnes
    # ==========================================================
    
    campagnes_actives = (
        db.query(Campagne)
        .filter(
            Campagne.entreprise_id == ent_id,
            Campagne.statut == "active"
        )
        .count()
    )
    
    campagnes_terminees = (
        db.query(Campagne)
        .filter(
            Campagne.entreprise_id == ent_id,
            Campagne.statut == "terminee"
        )
        .count()
    )
    
    # ==========================================================
    # Abonnement
    # ==========================================================
    
    abonnement = (
        db.query(Abonnement)
        .filter(Abonnement.entreprise_id == ent_id)
        .first()
    )
    
    # ==========================================================
    # Métriques calculées
    # ==========================================================
    
    # Taux de conversion global
    taux_conversion = None
    if offres_total > 0 and candidatures_total > 0:
        taux_conversion = round((candidatures_total / offres_total) * 100, 2)
    
    # Taux de candidatures traitées
    candidatures_traitees = sum(
        count for statut, count in candidatures_par_statut.items()
        if statut not in ["recue", "refusee"]
    )
    taux_traitement = None
    if candidatures_total > 0:
        taux_traitement = round((candidatures_traitees / candidatures_total) * 100, 2)
    
    # Taux d'embauche
    embauches = candidatures_par_statut.get("embauche", 0)
    taux_embauche = None
    if candidatures_total > 0:
        taux_embauche = round((embauches / candidatures_total) * 100, 2)
    
    # ==========================================================
    # Construction de la réponse
    # ==========================================================
    
    stats = AdminStats(
        # Statistiques de base
        utilisateurs_actifs=utilisateurs_actifs,
        recruteurs=recruteurs,
        offres_total=offres_total,
        candidatures_total=candidatures_total,
        
        # Statistiques additionnelles
        campagnes_actives=campagnes_actives,
        taux_conversion=taux_conversion,
        temps_moyen_recrutement=None,  # À implémenter avec les dates
        
        # Métriques enrichies
        admins_rh=admins_rh,
        evaluateurs=evaluateurs,
        offres_publiees=offres_publiees,
        offres_brouillon=offres_brouillon,
        campagnes_terminees=campagnes_terminees,
        candidatures_par_statut=candidatures_par_statut,
        taux_traitement=taux_traitement,
        taux_embauche=taux_embauche,
        embauches=embauches,
        
        # Abonnement
        plan=abonnement.plan if abonnement else None,
        statut_abonnement=abonnement.statut if abonnement else None,
        jours_restants=abonnement.jours_restants if abonnement else None,
        est_expire=abonnement.est_expire if abonnement else None,
    )
    
    # Mettre en cache (30 secondes)
    await cache.set(cache_key, stats.model_dump(), ttl=30)
    
    return success(stats)


@router.delete("/cache")
async def clear_admin_cache(
    user: Utilisateur = Depends(get_current_user),
):
    """
    Vide le cache des statistiques admin.
    
    **Permissions :** Admin RH ou Admin Plateforme uniquement.
    """
    if user.role not in (RoleUtilisateur.admin_rh, RoleUtilisateur.admin_plateforme):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé aux administrateurs."
        )
    
    cache_key = f"admin_stats:{user.entreprise_id}"
    await cache.delete(cache_key)
    
    return success(
        message="Cache des statistiques vidé avec succès."
    )