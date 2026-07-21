"""Schémas Abonnement + stats du dashboard admin."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import PlanAbonnement, StatutAbonnement


class AbonnementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    plan: PlanAbonnement
    statut: StatutAbonnement
    date_debut: datetime
    date_fin: datetime


class ChangePlanRequest(BaseModel):
    plan: PlanAbonnement


class PlanCatalogItem(BaseModel):
    plan: PlanAbonnement
    label: str
    prix: str
    features: list[str]


class AdminStats(BaseModel):
    """Indicateurs du dashboard admin, scopés au tenant courant."""

    utilisateurs_actifs: int
    recruteurs: int
    offres_total: int
    candidatures_total: int
    plan: PlanAbonnement | None = None
    statut_abonnement: StatutAbonnement | None = None
