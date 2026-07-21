"""Routes API pour la gestion des Campagnes de recrutement (CDC §6)."""

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.core.enums import RoleUtilisateur
from app.models.campagne import Campagne
from app.models.utilisateur import Utilisateur
from app.schemas.campagne import CampagneCreate, CampagneResponse, CampagneUpdate

router = APIRouter(prefix="/campagnes", tags=["Campagnes"])

# Dépendance réutilisée par tous les endpoints de ce fichier : seuls les
# recruteurs et admin RH de l'entreprise peuvent gérer les campagnes (CDC §6).
_require_recruteur_ou_admin = require_roles(
    RoleUtilisateur.recruteur, RoleUtilisateur.admin_rh
)


@router.post("", response_model=CampagneResponse, status_code=status.HTTP_201_CREATED)
async def create_campagne(
    campagne_in: CampagneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Campagne:
    """Créer une nouvelle campagne de recrutement rattachée à l'entreprise de l'utilisateur."""
    if not current_user.entreprise_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'utilisateur n'est rattaché à aucune entreprise.",
        )

    campagne_data = campagne_in.model_dump()
    campagne = Campagne(**campagne_data, entreprise_id=current_user.entreprise_id)

    db.add(campagne)
    await db.commit()
    await db.refresh(campagne)

    return campagne


@router.get("", response_model=list[CampagneResponse])
async def list_campagnes(
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Sequence[Campagne]:
    """Lister toutes les campagnes appartenant à l'entreprise de l'utilisateur connecté."""
    if not current_user.entreprise_id:
        return []

    stmt = select(Campagne).where(Campagne.entreprise_id == current_user.entreprise_id)
    result = await db.execute(stmt)

    return result.scalars().all()


@router.get("/{campagne_id}", response_model=CampagneResponse)
async def get_campagne(
    campagne_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Campagne:
    """Récupérer le détail d'une campagne spécifique."""
    stmt = select(Campagne).where(
        Campagne.id == campagne_id,
        Campagne.entreprise_id == current_user.entreprise_id,
    )
    result = await db.execute(stmt)
    campagne = result.scalar_one_or_none()

    if not campagne:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campagne non trouvée.",
        )

    return campagne


@router.put("/{campagne_id}", response_model=CampagneResponse)
async def update_campagne(
    campagne_id: uuid.UUID,
    campagne_in: CampagneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(_require_recruteur_ou_admin),
) -> Campagne:
    """Mettre à jour les informations d'une campagne."""
    stmt = select(Campagne).where(
        Campagne.id == campagne_id,
        Campagne.entreprise_id == current_user.entreprise_id,
    )
    result = await db.execute(stmt)
    campagne = result.scalar_one_or_none()

    if not campagne:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campagne non trouvée.",
        )

    update_data = campagne_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campagne, field, value)

    await db.commit()
    await db.refresh(campagne)

    return campagne
