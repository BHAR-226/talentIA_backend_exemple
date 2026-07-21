"""Routes API pour la gestion des Offres d'emploi (CDC §7)."""

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.core.enums import RoleUtilisateur, StatutOffre
from app.models.campagne import Campagne
from app.models.offre import Offre
from app.models.utilisateur import Utilisateur
from app.schemas.offre import OffreCreate, OffreResponse, OffreUpdate, ReceptionUpdate

router = APIRouter(prefix="/offres", tags=["Offres"])

# Dépendance réutilisée par tous les endpoints de ce fichier : seuls les
# recruteurs et admin RH de l'entreprise peuvent gérer les offres (CDC §7).
_require_recruteur_ou_admin = require_roles(
    RoleUtilisateur.recruteur, RoleUtilisateur.admin_rh
)


async def _get_offre_for_user(
    offre_id: uuid.UUID,
    user: Utilisateur,
    db: AsyncSession,
) -> Offre:
    """Fonction utilitaire pour vérifier qu'une offre existe
    et qu'elle appartient bien à l'entreprise de l'utilisateur connecté.
    """
    stmt = (
        select(Offre)
        .join(Campagne, Offre.campagne_id == Campagne.id)
        .where(
            Offre.id == offre_id,
            Campagne.entreprise_id == user.entreprise_id,
        )
    )
    result = await db.execute(stmt)
    offre = result.scalar_one_or_none()

    if not offre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Offre non trouvée ou accès non autorisé.",
        )
    return offre


@router.post("", response_model=OffreResponse, status_code=status.HTTP_201_CREATED)
async def create_offre(
    offre_in: OffreCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Offre:
    """Créer une nouvelle offre rattachée à une campagne de l'entreprise."""
    # 1. Vérifier que la campagne ciblée appartient bien à l'entreprise de l'utilisateur
    stmt = select(Campagne).where(
        Campagne.id == offre_in.campagne_id,
        Campagne.entreprise_id == current_user.entreprise_id,
    )
    result = await db.execute(stmt)
    campagne = result.scalar_one_or_none()

    if not campagne:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campagne associée non trouvée.",
        )

    # 2. Création de l'offre
    offre_data = offre_in.model_dump()
    offre = Offre(
        **offre_data,
        createur_id=current_user.id,
    )

    db.add(offre)
    await db.commit()
    await db.refresh(offre)

    return offre


@router.get("", response_model=list[OffreResponse])
async def list_offres(
    statut: StatutOffre | None = Query(
        None,
        description="Filtrer par statut (brouillon, publiee...)",
    ),
    campagne_id: uuid.UUID | None = Query(None, description="Filtrer par campagne"),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Sequence[Offre]:
    """Lister les offres de l'entreprise (filtres optionnels par statut ou campagne)."""
    if not current_user.entreprise_id:
        return []

    # Requête avec JOIN pour vérifier la propriété via la campagne
    stmt = (
        select(Offre)
        .join(Campagne, Offre.campagne_id == Campagne.id)
        .where(Campagne.entreprise_id == current_user.entreprise_id)
    )

    if statut:
        stmt = stmt.where(Offre.statut == statut)
    if campagne_id:
        stmt = stmt.where(Offre.campagne_id == campagne_id)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{offre_id}", response_model=OffreResponse)
async def get_offre(
    offre_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Offre:
    """Récupérer le détail d'une offre."""
    return await _get_offre_for_user(offre_id, current_user, db)


@router.put("/{offre_id}", response_model=OffreResponse)
async def update_offre(
    offre_id: uuid.UUID,
    offre_in: OffreUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Offre:
    """Mettre à jour les données d'une offre."""
    offre = await _get_offre_for_user(offre_id, current_user, db)

    update_data = offre_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(offre, field, value)

    await db.commit()
    await db.refresh(offre)

    return offre


@router.put("/{offre_id}/reception", response_model=OffreResponse)
async def toggle_reception_candidatures(
    offre_id: uuid.UUID,
    reception_in: ReceptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Offre:
    """Arrêter ou réouvrir la réception des candidatures pour une offre.
    C'est la route appelée par le bouton « Arrêter » du Frontend.
    """
    offre = await _get_offre_for_user(offre_id, current_user, db)

    # Mise à jour de l'état de réception
    offre.reception_ouverte = reception_in.reception_ouverte

    await db.commit()
    await db.refresh(offre)

    return offre


@router.delete("/{offre_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offre(
    offre_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> None:
    """Supprimer une offre d'emploi."""
    offre = await _get_offre_for_user(offre_id, current_user, db)

    await db.delete(offre)
    await db.commit()