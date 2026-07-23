"""Routes API pour la gestion des Campagnes de recrutement (CDC §6)."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.enums import RoleUtilisateur
from app.core.responses import success
from app.models.campagne import Campagne
from app.models.utilisateur import Utilisateur
from app.schemas.campagne import CampagneCreate, CampagneResponse, CampagneUpdate

router = APIRouter(prefix="/campagnes", tags=["campagnes"])

# Statuts valides pour une campagne (cf. modèle Campagne.statut)
STATUTS_VALIDES = ("active", "terminee", "annulee")


# ==========================================================
# Fonctions utilitaires
# ==========================================================

def _get_campagne_or_404(db: Session, campagne_id: uuid.UUID, entreprise_id: uuid.UUID) -> Campagne:
    """Récupère une campagne en vérifiant l'appartenance à l'entreprise."""
    campagne = (
        db.query(Campagne)
        .filter(
            Campagne.id == campagne_id,
            Campagne.entreprise_id == entreprise_id,
            Campagne.deleted_at.is_(None),
        )
        .first()
    )
    if campagne is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campagne introuvable ou accès non autorisé."
        )
    return campagne


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
def lister_campagnes(
    user: Utilisateur = Depends(get_current_user),
    statut: Optional[str] = Query(
        None, description="Filtrer par statut (active, terminee, annulee)"
    ),
    search: Optional[str] = Query(None, description="Rechercher par intitulé"),
    db: Session = Depends(get_db),
):
    """
    Liste toutes les campagnes de l'entreprise.

    **Filtres disponibles :**
    - `statut` : Filtrer par statut (active, terminee, annulee)
    - `search` : Recherche textuelle dans l'intitulé
    """
    query = db.query(Campagne).filter(
        Campagne.entreprise_id == user.entreprise_id,
        Campagne.deleted_at.is_(None),
    )

    if statut:
        query = query.filter(Campagne.statut == statut)

    if search:
        query = query.filter(Campagne.intitule.ilike(f"%{search}%"))

    campagnes = query.order_by(Campagne.created_at.desc()).all()
    return success([CampagneResponse.model_validate(c) for c in campagnes])


@router.post("", status_code=status.HTTP_201_CREATED)
def creer_campagne(
    payload: CampagneCreate,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Crée une nouvelle campagne de recrutement.

    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)

    campagne = Campagne(
        entreprise_id=user.entreprise_id,
        intitule=payload.intitule,
        departement=payload.departement,
        date_limite=payload.date_limite,
        nombre_postes=payload.nombre_postes,
        localisation=payload.localisation,
        competences=payload.competences or [],
        experience_requise=payload.experience_requise,
        langues=payload.langues or [],
        niveau_etudes=payload.niveau_etudes,
        type_contrat=payload.type_contrat,
        salaire_min=payload.salaire_min,
        salaire_max=payload.salaire_max,
        recruteurs_responsables=payload.recruteurs_responsables or [],
        description=payload.description,
        workflow=payload.workflow or [],
    )

    db.add(campagne)
    db.commit()
    db.refresh(campagne)

    return success(
        CampagneResponse.model_validate(campagne),
        "Campagne créée avec succès."
    )


@router.get("/{campagne_id}")
def get_campagne(
    campagne_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Récupère une campagne par son ID."""
    campagne = _get_campagne_or_404(db, campagne_id, user.entreprise_id)
    return success(CampagneResponse.model_validate(campagne))


@router.put("/{campagne_id}")
def update_campagne(
    campagne_id: uuid.UUID,
    payload: CampagneUpdate,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Met à jour une campagne existante.

    **Permissions :** Recruteur ou Admin RH.
    **Restriction :** Une campagne terminée ou annulée ne peut être modifiée
    que par un admin RH.
    """
    _check_recruteur_or_admin(user)
    campagne = _get_campagne_or_404(db, campagne_id, user.entreprise_id)

    if campagne.statut != "active" and user.role != RoleUtilisateur.admin_rh:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de modifier une campagne terminée ou annulée."
        )

    data = payload.model_dump(exclude_unset=True)

    if "statut" in data and data["statut"] not in STATUTS_VALIDES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Statut invalide. Valeurs autorisées : {', '.join(STATUTS_VALIDES)}."
        )

    for champ, valeur in data.items():
        setattr(campagne, champ, valeur)

    db.commit()
    db.refresh(campagne)

    return success(
        CampagneResponse.model_validate(campagne),
        "Campagne mise à jour avec succès."
    )


# ==========================================================
# Actions sur les campagnes
# ==========================================================

@router.post("/{campagne_id}/terminer")
def terminer_campagne(
    campagne_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Marque une campagne comme terminée.

    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)
    campagne = _get_campagne_or_404(db, campagne_id, user.entreprise_id)

    if campagne.est_terminee or campagne.statut == "terminee":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette campagne est déjà terminée."
        )

    campagne.terminer()
    db.commit()
    db.refresh(campagne)

    return success(
        CampagneResponse.model_validate(campagne),
        "Campagne marquée comme terminée."
    )


@router.post("/{campagne_id}/annuler")
def annuler_campagne(
    campagne_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Annule une campagne (archive également ses offres publiées).

    **Permissions :** Recruteur ou Admin RH.
    """
    _check_recruteur_or_admin(user)
    campagne = _get_campagne_or_404(db, campagne_id, user.entreprise_id)

    if campagne.est_annulee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette campagne est déjà annulée."
        )

    campagne.annuler()
    db.commit()
    db.refresh(campagne)

    return success(
        CampagneResponse.model_validate(campagne),
        "Campagne annulée avec succès."
    )


@router.post("/{campagne_id}/reactiver")
def reactiver_campagne(
    campagne_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Réactive une campagne terminée ou annulée.

    **Permissions :** Admin RH uniquement.
    """
    _check_admin_rh(user)
    campagne = _get_campagne_or_404(db, campagne_id, user.entreprise_id)

    if campagne.est_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette campagne est déjà active."
        )

    campagne.reactiver()
    db.commit()
    db.refresh(campagne)

    return success(
        CampagneResponse.model_validate(campagne),
        "Campagne réactivée avec succès."
    )


# ==========================================================
# Suppression
# ==========================================================

@router.delete("/{campagne_id}")
def delete_campagne(
    campagne_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Supprime une campagne (uniquement si elle n'a pas d'offres).

    **Permissions :** Admin RH uniquement.
    """
    _check_admin_rh(user)
    campagne = _get_campagne_or_404(db, campagne_id, user.entreprise_id)

    if campagne.nombre_offres > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer une campagne contenant des offres."
        )

    campagne.soft_delete(user.id)
    db.commit()

    return success(message="Campagne supprimée avec succès.")


# ==========================================================
# Statistiques
# ==========================================================

@router.get("/{campagne_id}/stats")
def stats_campagne(
    campagne_id: uuid.UUID,
    user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Statistiques détaillées d'une campagne.

    **Statistiques retournées :**
    - Nombre d'offres associées
    - Nombre de postes pourvus / total
    - Taux de remplissage
    """
    campagne = _get_campagne_or_404(db, campagne_id, user.entreprise_id)

    stats = {
        "id": str(campagne.id),
        "intitule": campagne.intitule,
        "statut": campagne.statut,
        "nombre_offres": campagne.nombre_offres,
        "nombre_postes": campagne.nombre_postes,
        "nombre_postes_pourvus": campagne.nombre_postes_pourvus,
        "taux_remplissage": campagne.taux_remplissage,
        "est_terminee": campagne.est_terminee,
        "est_active": campagne.est_active,
        "date_limite": campagne.date_limite,
    }

    return success(stats)
