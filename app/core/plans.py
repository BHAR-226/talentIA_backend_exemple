"""Catalogue des plans d'abonnement (aligné cahier des charges §4).

Prix en FCFA/mois — valeurs indicatives ; la facturation réelle est hors
périmètre MVP. Source unique pour l'endpoint `GET /abonnements/plans`.
"""

from app.core.enums import PlanAbonnement

PLAN_CATALOG: dict[PlanAbonnement, dict] = {
    PlanAbonnement.starter: {
        "label": "Starter",
        "prix": "45 000",
        "features": ["3 recruteurs", "10 offres", "IA basique"],
    },
    PlanAbonnement.business: {
        "label": "Business",
        "prix": "120 000",
        "features": [
            "Recruteurs illimités",
            "IA avancée",
            "Visioconférence intégrée",
            "Accès API",
        ],
    },
    PlanAbonnement.enterprise: {
        "label": "Enterprise",
        "prix": "Sur devis",
        "features": [
            "Multi-filiales",
            "SSO",
            "Workflows personnalisés",
            "IA premium",
            "Reporting avancé",
        ],
    },
}
