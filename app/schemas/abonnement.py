"""Schémas Abonnement + stats du dashboard admin."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PlanAbonnement, StatutAbonnement


class AbonnementResponse(BaseModel):
    """Réponse complète d'un abonnement avec toutes ses métriques."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    plan: PlanAbonnement
    statut: StatutAbonnement
    date_debut: datetime
    date_fin: datetime

    # Champs de suivi
    renouvellement_auto: bool = Field(
        default=False,
        description="Indique si l'abonnement se renouvelle automatiquement"
    )
    derniere_renouvellement: datetime | None = Field(
        default=None,
        description="Date du dernier renouvellement"
    )

    # Propriétés calculées
    jours_restants: int = Field(
        description="Nombre de jours restants avant expiration"
    )
    est_expire: bool = Field(
        description="Indique si l'abonnement est expiré"
    )


class ChangePlanRequest(BaseModel):
    """Requête pour changer de plan d'abonnement."""
    plan: PlanAbonnement = Field(description="Nouveau plan d'abonnement")


class PlanCatalogItem(BaseModel):
    """Élément du catalogue des plans d'abonnement disponibles."""
    plan: PlanAbonnement = Field(description="Identifiant du plan")
    label: str = Field(description="Nom affichable du plan")
    prix: str = Field(description="Prix du plan (format texte)")
    features: list[str] = Field(description="Liste des fonctionnalités incluses")


class AdminStats(BaseModel):
    """Indicateurs du dashboard admin, scopés au tenant courant."""

    # Statistiques RH
    utilisateurs_actifs: int = Field(description="Nombre d'utilisateurs actifs")
    recruteurs: int = Field(description="Nombre de recruteurs")
    offres_total: int = Field(description="Nombre total d'offres")
    candidatures_total: int = Field(description="Nombre total de candidatures")

    # Métriques de performance
    campagnes_actives: int | None = Field(
        default=0,
        description="Nombre de campagnes actives"
    )
    taux_conversion: float | None = Field(
        default=None,
        description="Taux de conversion (candidatures / offres) en pourcentage"
    )
    temps_moyen_recrutement: float | None = Field(
        default=None,
        description="Temps moyen de recrutement en jours"
    )

    # Abonnement
    plan: PlanAbonnement | None = Field(
        default=None,
        description="Plan d'abonnement actuel"
    )
    statut_abonnement: StatutAbonnement | None = Field(
        default=None,
        description="Statut de l'abonnement"
    )
