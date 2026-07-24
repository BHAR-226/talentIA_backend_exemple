"""Routes API pour la gestion des Offres d'emploi (CDC §7)."""

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.core.enums import RoleUtilisateur, StatutOffre
from app.models.campagne import Campagne
from app.models.offre import Offre
from app.models.utilisateur import Utilisateur
from app.schemas.offre import (
    OffreCreate,
    OffreResponse,
    OffreUpdate,
    ReceptionUpdate,
)


router = APIRouter(
    prefix="/offres",
    tags=["Offres"],
)


# Seuls les recruteurs et admin RH peuvent gérer les offres
_require_recruteur_ou_admin = require_roles(
    RoleUtilisateur.recruteur,
    RoleUtilisateur.admin_rh,
)


def _get_offre_for_user(
    offre_id: uuid.UUID,
    user: Utilisateur,
    db: Session,
) -> Offre:
    """
    Vérifie qu'une offre existe et appartient
    bien à l'entreprise de l'utilisateur connecté.
    """

    stmt = (
        select(Offre)
        .join(Campagne, Offre.campagne_id == Campagne.id)
        .where(
            Offre.id == offre_id,
            Campagne.entreprise_id == user.entreprise_id,
        )
    )

    result = db.execute(stmt)
    offre = result.scalar_one_or_none()

    if not offre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre non trouvée ou accès non autorisé.",
        )

    return offre


# ==========================================================
# Création
# ==========================================================


@router.post(
    "",
    response_model=OffreResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_offre(
    offre_in: OffreCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Offre:
    """
    Créer une nouvelle offre rattachée à une campagne.
    """

    stmt = select(Campagne).where(
        Campagne.id == offre_in.campagne_id,
        Campagne.entreprise_id == current_user.entreprise_id,
    )

    result = db.execute(stmt)
    campagne = result.scalar_one_or_none()

    if not campagne:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campagne associée non trouvée.",
        )

    offre_data = offre_in.model_dump()

    offre = Offre(
        **offre_data,
        createur_id=current_user.id,
    )

    db.add(offre)
    db.commit()
    db.refresh(offre)

    return offre


# ==========================================================
# Liste
# ==========================================================


@router.get(
    "",
    response_model=list[OffreResponse],
)
def list_offres(
    statut: StatutOffre | None = Query(
        None,
        description="Filtrer par statut",
    ),
    campagne_id: uuid.UUID | None = Query(
        None,
    ),
    db: Session = Depends(get_db),
) -> Sequence[Offre]:
    """
    Liste les offres.

    Endpoint public pour le frontend candidat :
    GET /offres?statut=publiee
    """

    stmt = select(Offre)

    if statut:
        stmt = stmt.where(
            Offre.statut == statut
        )

    if campagne_id:
        stmt = stmt.where(
            Offre.campagne_id == campagne_id
        )

    result = db.execute(stmt)

    return result.scalars().all()


# ==========================================================
# Détail
# ==========================================================


@router.get(
    "/{offre_id}",
    response_model=OffreResponse,
)
def get_offre(
    offre_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Offre:

    return _get_offre_for_user(
        offre_id,
        current_user,
        db,
    )


# ==========================================================
# Modification
# ==========================================================


@router.put(
    "/{offre_id}",
    response_model=OffreResponse,
)
def update_offre(
    offre_id: uuid.UUID,
    offre_in: OffreUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Offre:

    offre = _get_offre_for_user(
        offre_id,
        current_user,
        db,
    )

    update_data = offre_in.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(
            offre,
            field,
            value,
        )

    db.commit()
    db.refresh(offre)

    return offre


# ==========================================================
# Réception candidatures
# ==========================================================


@router.put(
    "/{offre_id}/reception",
    response_model=OffreResponse,
)
def toggle_reception_candidatures(
    offre_id: uuid.UUID,
    reception_in: ReceptionUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Offre:

    offre = _get_offre_for_user(
        offre_id,
        current_user,
        db,
    )

    offre.reception_ouverte = (
        reception_in.reception_ouverte
    )

    db.commit()
    db.refresh(offre)

    return offre


# ==========================================================
# Suppression
# ==========================================================


@router.delete(
    "/{offre_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_offre(
    offre_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> None:

    offre = _get_offre_for_user(
        offre_id,
        current_user,
        db,
    )

    db.delete(offre)
    db.commit()