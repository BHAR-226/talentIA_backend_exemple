"""Routes API pour la gestion des Offres d'emploi (CDC §7)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.enums import RoleUtilisateur, StatutOffre
from app.core.plans import get_plan_limits
from app.core.responses import success
from app.models.abonnement import Abonnement
from app.models.campagne import Campagne
from app.models.offre import Offre
from app.models.utilisateur import Utilisateur
from app.schemas.offre import OffreCreate, OffreReceptionUpdate, OffreResponse, OffreUpdate

router = APIRouter(prefix="/offres", tags=["offres"])


def _check_quota_offres_actives(db: Session, entreprise_id: uuid.UUID) -> None:
    """Vérifie que l'entreprise n'a pas atteint son quota d'offres actives (publiées)."""
    abonnement = (
        db.query(Abonnement)
        .filter(Abonnement.entreprise_id == entreprise_id)
        .first()
    )
    if abonnement is None:
        return

    limite = get_plan_limits(abonnement.plan).get("offres_actives")
    if limite is None:
        return

    nb_actives = (
        db.query(Offre)
        .join(Campagne)
        .filter(
            Campagne.entreprise_id == entreprise_id,
            Campagne.deleted_at.is_(None),
            Offre.deleted_at.is_(None),
            Offre.statut == StatutOffre.publiee,
        )
        .count()
    )
    if nb_actives >= limite:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Quota d'offres actives atteint pour le plan '{abonnement.plan.value}' "
                f"({limite} maximum). Archivez une offre existante ou passez à un plan "
                "supérieur."
            )
        )


# ==========================================================
# Fonctions utilitaires
# ==========================================================

def _get_offre_or_404(db: Session, offre_id: uuid.UUID, entreprise_id: uuid.UUID) -> Offre:
    """Récupère une offre en vérifiant l'appartenance à l'entreprise."""
    offre = (
        db.query(Offre)
        .join(Campagne)
        .filter(
            Offre.id == offre_id,
            Campagne.entreprise_id == entreprise_id,
            Campagne.deleted_at.is_(None),  # Soft delete (campagne parente)
            Offre.deleted_at.is_(None)  # Soft delete
        )
        .first()
    )
    if offre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre introuvable ou accès non autorisé."
        )

    return offre


def _check_recruteur_or_admin(user: Utilisateur) -> None:
    """Vérifie que l'utilisateur est recruteur ou admin RH."""
    if user.role not in (RoleUtilisateur.recruteur, RoleUtilisateur.admin_rh):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé aux recruteurs et administrateurs RH."
        )


def _check_admin_rh(user: Utilisateur) -> None:
    """Vérifie que l'utilisateur est admin RH."""
    if user.role != RoleUtilisateur.admin_rh:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé aux administrateurs RH."
        )


# ==========================================================
# Routes CRUD
# ==========================================================

@router.get("")
def lister_offres(
    user: Utilisateur = Depends(get_current_user),
    statut: str | None = Query(None, description="Filtrer par statut (brouillon, publiee, archivee)"),
    campagne_id: uuid.UUID | None = Query(None, description="Filtrer par campagne"),
    search: str | None = Query(None, description="Rechercher par titre"),
    visible: bool | None = Query(None, description="Filtrer par visibilité"),
    db: Session = Depends(get_db),
):
    """Liste toutes les offres de l'entreprise.
    
    **Filtres disponibles :**
    - `statut` : Filtrer par statut (brouillon, publiee, archivee)
    - `campagne_id` : Filtrer par campagne
    - `search` : Recherche textuelle dans le titre
    - `visible` : Filtrer par visibilité (true/false)
    """
    query = (
        db.query(Offre)
        .join(Campagne)
        .filter(
            Campagne.entreprise_id == user.entreprise_id,
            Campagne.deleted_at.is_(None),
            Offre.deleted_at.is_(None)
        )
    )

    if statut:
        query = query.filter(Offre.statut == statut)

    if campagne_id:
        query = query.filter(Offre.campagne_id == campagne_id)

    if search:
        query = query.filter(Offre.titre.ilike(f"%{search}%"))

    if visible is not None:
        query = query.filter(Offre.visible == visible)

    offres = query.order_by(Offre.created_at.desc()).all()
    return success([OffreResponse.model_validate(o) for o in offres])


@router.post("", status_code=status.HTTP_201_CREATED)
def creer_offre(
    payload: OffreCreate,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crée une nouvelle offre d'emploi.
    
    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)

    # Vérifier que la campagne existe et appartient à l'entreprise
    campagne = (
        db.query(Campagne)
        .filter(
            Campagne.id == payload.campagne_id,
            Campagne.entreprise_id == user.entreprise_id,
            Campagne.deleted_at.is_(None)
        )
        .first()
    )
    if campagne is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campagne associée non trouvée."
        )

    # Vérifier que la campagne n'est pas terminée
    if campagne.est_terminee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de créer une offre dans une campagne terminée."
        )

    offre = Offre(
        campagne_id=payload.campagne_id,
        createur_id=user.id,
        titre=payload.titre,
        description=payload.description,
        type_contrat=payload.type_contrat,
        localisation=payload.localisation,
        salaire_min=payload.salaire_min,
        salaire_max=payload.salaire_max,
        champs_personnalises_def=payload.champs_personnalises_def or [],
        competences_requises=payload.competences_requises or [],
        missions=payload.missions or [],
        soft_skills=payload.soft_skills or [],
        avantages=payload.avantages or [],
        tele_travail=payload.tele_travail,
        visible=payload.visible,
        statut=StatutOffre.brouillon,
        date_limite=payload.date_limite,
    )

    db.add(offre)
    db.commit()
    db.refresh(offre)

    return success(
        OffreResponse.model_validate(offre),
        "Offre créée avec succès."
    )


@router.get("/publiques")
def lister_offres_publiques(
    entreprise_id: uuid.UUID | None = Query(
        None,
        description="Scoper la liste aux offres d'une entreprise précise",
    ),
    db: Session = Depends(get_db),
):
    """Liste les offres visibles publiquement (vue candidat, P2.5).

    **Filtres appliqués :** seules les offres encore accessibles aux
    candidats sont renvoyées :
    - `statut` == `publiee`
    - `visible` == `true`
    - `reception_ouverte` == `true`
    - `date_limite` absente ou non dépassée
    - campagne parente non supprimée (soft delete)

    **Aucune authentification requise** (bord publique candidat).
    """
    query = (
        db.query(Offre)
        .join(Campagne)
        .filter(
            Campagne.deleted_at.is_(None),
            Offre.deleted_at.is_(None),
            Offre.statut == StatutOffre.publiee,
            Offre.visible.is_(True),
            Offre.reception_ouverte.is_(True),
            or_(
                Offre.date_limite.is_(None),
                Offre.date_limite >= datetime.now(UTC),
            ),
        )
    )

    if entreprise_id is not None:
        query = query.filter(Campagne.entreprise_id == entreprise_id)

    offres = query.order_by(Offre.created_at.desc()).all()
    return success([OffreResponse.model_validate(o) for o in offres])


@router.get("/{offre_id}")
def get_offre(
    offre_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Récupère une offre par son ID."""
    offre = _get_offre_or_404(db, offre_id, user.entreprise_id)
    return success(OffreResponse.model_validate(offre))


@router.put("/{offre_id}")
def update_offre(
    offre_id: uuid.UUID,
    payload: OffreUpdate,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Met à jour une offre existante.
    
    **Permissions :** Recruteur ou Admin RH.
    **Restriction :** Une offre publiée ou archivée ne peut être modifiée que par un admin RH.
    """
    _check_recruteur_or_admin(user)
    offre = _get_offre_or_404(db, offre_id, user.entreprise_id)

    # Ne pas modifier une offre publiée ou archivée (sauf admin RH)
    if offre.statut != StatutOffre.brouillon and user.role != RoleUtilisateur.admin_rh:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de modifier une offre publiée ou archivée."
        )

    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(offre, champ, valeur)

    db.commit()
    db.refresh(offre)

    return success(
        OffreResponse.model_validate(offre),
        "Offre mise à jour avec succès."
    )


# ==========================================================
# Actions sur les offres
# ==========================================================

@router.post("/{offre_id}/publier")
def publier_offre(
    offre_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publie une offre (la rend visible aux candidats).
    
    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)
    offre = _get_offre_or_404(db, offre_id, user.entreprise_id)

    if offre.est_publiee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette offre est déjà publiée."
        )

    _check_quota_offres_actives(db, user.entreprise_id)

    offre.publier()
    db.commit()
    db.refresh(offre)

    return success(
        OffreResponse.model_validate(offre),
        "Offre publiée avec succès."
    )


@router.post("/{offre_id}/archiver")
def archiver_offre(
    offre_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Archive une offre.
    
    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)
    offre = _get_offre_or_404(db, offre_id, user.entreprise_id)

    if offre.est_archivee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette offre est déjà archivée."
        )

    offre.archiver()
    db.commit()
    db.refresh(offre)

    return success(
        OffreResponse.model_validate(offre),
        "Offre archivée avec succès."
    )


@router.put("/{offre_id}/reception")
def toggle_reception_offre(
    offre_id: uuid.UUID,
    payload: OffreReceptionUpdate,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Active ou désactive la réception des candidatures (bouton Arrêter/Rouvrir).
    
    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)
    offre = _get_offre_or_404(db, offre_id, user.entreprise_id)

    # Vérifier que l'offre est publiée
    if not offre.est_publiee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seules les offres publiées peuvent accepter des candidatures."
        )

    offre.reception_ouverte = payload.reception_ouverte
    db.commit()
    db.refresh(offre)

    message = "Réception des candidatures ouverte." if payload.reception_ouverte else "Réception des candidatures arrêtée."
    return success(OffreResponse.model_validate(offre), message)


@router.post("/{offre_id}/dupliquer")
def dupliquer_offre(
    offre_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Duplique une offre (crée une copie en brouillon).
    
    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)
    offre = _get_offre_or_404(db, offre_id, user.entreprise_id)

    nouvelle_offre = offre.dupliquer()
    db.add(nouvelle_offre)
    db.commit()
    db.refresh(nouvelle_offre)

    return success(
        OffreResponse.model_validate(nouvelle_offre),
        "Offre dupliquée avec succès."
    )


# ==========================================================
# Suppression
# ==========================================================

@router.delete("/{offre_id}")
def delete_offre(
    offre_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Supprime une offre (uniquement si elle n'a pas de candidatures).
    
    **Permissions :** Admin RH uniquement.
    """
    _check_admin_rh(user)
    offre = _get_offre_or_404(db, offre_id, user.entreprise_id)

    # Vérifier qu'il n'y a pas de candidatures
    candidatures_count = sum(1 for c in offre.candidatures if not c.is_deleted)
    if candidatures_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer une offre avec des candidatures."
        )

    # Soft delete
    offre.soft_delete(user.id)
    db.commit()

    return success(message="Offre supprimée avec succès.")


# ==========================================================
# Statistiques
# ==========================================================

@router.get("/{offre_id}/stats")
def stats_offre(
    offre_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Statistiques détaillées d'une offre.
    
    **Statistiques retournées :**
    - Nombre total de candidatures
    - Nombre de candidatures par statut
    - Taux de conversion
    - Nombre de candidatures reçues
    - Nombre de candidatures analysées
    """
    offre = _get_offre_or_404(db, offre_id, user.entreprise_id)

    # Compter les candidatures par statut
    stats_par_statut = {}
    for c in offre.candidatures:
        if not c.is_deleted:
            statut = c.statut.value
            stats_par_statut[statut] = stats_par_statut.get(statut, 0) + 1

    stats = {
        "id": str(offre.id),
        "titre": offre.titre,
        "statut": offre.statut.value,
        "nombre_candidatures": offre.nombre_candidatures,
        "nombre_candidatures_recues": offre.nombre_candidatures_recues,
        "nombre_candidatures_analysees": offre.nombre_candidatures_analysees,
        "stats_par_statut": stats_par_statut,
        "taux_conversion": offre.taux_conversion,
        "est_pourvue": offre.est_pourvue,
        "est_visible": offre.est_visible,
        "est_ouverte": offre.est_ouverte,
        "date_publication": offre.date_publication,
        "reception_ouverte": offre.reception_ouverte,
    }

    return success(stats)
