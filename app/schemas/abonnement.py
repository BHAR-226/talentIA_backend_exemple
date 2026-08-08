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
    admins_rh: int = Field(
        default=0,
        description="Nombre d'administrateurs RH"
    )
    evaluateurs: int = Field(
        default=0,
        description="Nombre d'évaluateurs techniques"
    )
    offres_total: int = Field(description="Nombre total d'offres")
    candidatures_total: int = Field(description="Nombre total de candidatures")

    # Métriques de performance
    campagnes_actives: int | None = Field(
        default=0,
        description="Nombre de campagnes actives"
    )
    campagnes_terminees: int | None = Field(
        default=0,
        description="Nombre de campagnes terminées"
    )
    offres_publiees: int | None = Field(
        default=0,
        description="Nombre d'offres publiées"
    )
    offres_brouillon: int | None = Field(
        default=0,
        description="Nombre d'offres en brouillon"
    )
    taux_conversion: float | None = Field(
        default=None,
        description="Taux de conversion (candidatures / offres) en pourcentage"
    )
    temps_moyen_recrutement: float | None = Field(
        default=None,
        description="Temps moyen de recrutement en jours"
    )

    # KPIs recrutement (P2.8)
    embauches: int = Field(
        default=0,
        description="Nombre de recrutements (candidatures embauchées)"
    )
    nombre_entretiens: int = Field(
        default=0,
        description="Nombre de candidatures au stade entretien (RH + métier)"
    )
    candidatures_par_statut: dict[str, int] = Field(
        default_factory=dict,
        description="Répartition des candidatures par statut"
    )
    taux_traitement: float | None = Field(
        default=None,
        description="Taux de candidatures traitées en pourcentage"
    )
    taux_embauche: float | None = Field(
        default=None,
        description="Taux d'embauche en pourcentage"
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
    jours_restants: int | None = Field(
        default=None,
        description="Nombre de jours restants avant expiration"
    )
    est_expire: bool | None = Field(
        default=None,
        description="Indique si l'abonnement est expiré"
    )
