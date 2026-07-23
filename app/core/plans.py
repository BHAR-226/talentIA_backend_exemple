"""Catalogue des plans d'abonnement (aligné cahier des charges §4).

Prix en FCFA/mois — valeurs indicatives ; la facturation réelle est hors
périmètre MVP. Source unique pour l'endpoint `GET /abonnements/plans`.
"""

from typing import Dict, List, Optional

from app.core.enums import PlanAbonnement


# ==========================================================
# Définition du catalogue
# ==========================================================

PLAN_CATALOG: Dict[PlanAbonnement, Dict] = {
    PlanAbonnement.starter: {
        "label": "Starter",
        "prix": "45 000",
        "prix_annuel": "486 000",  # 10% de réduction sur l'annuel
        "description": "Idéal pour les petites équipes qui débutent",
        "features": [
            "3 recruteurs",
            "10 offres actives",
            "IA basique (matching simple)",
            "Support email",
            "Tableau de bord basique",
        ],
        "limits": {
            "recruteurs": 3,
            "offres_actives": 10,
            "candidatures_par_offre": 100,
            "stockage_cv": "100 MB",
        },
        "recommended": False,
    },
    PlanAbonnement.business: {
        "label": "Business",
        "prix": "120 000",
        "prix_annuel": "1 296 000",  # 10% de réduction sur l'annuel
        "description": "Pour les équipes qui veulent passer à l'échelle",
        "features": [
            "Recruteurs illimités",
            "Offres illimitées",
            "IA avancée (matching intelligent)",
            "Visioconférence intégrée",
            "Accès API",
            "Support prioritaire",
            "Analytics avancés",
            "Intégration ATS",
        ],
        "limits": {
            "recruteurs": None,  # Illimité
            "offres_actives": None,  # Illimité
            "candidatures_par_offre": 500,
            "stockage_cv": "1 GB",
        },
        "recommended": True,
    },
    PlanAbonnement.enterprise: {
        "label": "Enterprise",
        "prix": "Sur devis",
        "prix_annuel": "Sur devis",
        "description": "Solution complète pour les grandes organisations",
        "features": [
            "Multi-filiales",
            "SSO (SAML/OIDC)",
            "Workflows personnalisés",
            "IA premium (matching avancé + prédictions)",
            "Reporting avancé",
            "Dédié : support 24/7, account manager",
            "Formation incluse",
            "On-premise possible",
            "Audit & conformité",
            "SLA personnalisé",
        ],
        "limits": {
            "recruteurs": None,  # Illimité
            "offres_actives": None,  # Illimité
            "candidatures_par_offre": None,  # Illimité
            "stockage_cv": "Illimité",
        },
        "recommended": False,
    },
}


# ==========================================================
# Fonctions utilitaires
# ==========================================================

def get_plan(plan: PlanAbonnement) -> Optional[Dict]:
    """
    Récupère les détails d'un plan.
    
    Args:
        plan: Plan d'abonnement
        
    Returns:
        Dict: Détails du plan ou None si inexistant
    """
    return PLAN_CATALOG.get(plan)


def get_plan_features(plan: PlanAbonnement) -> List[str]:
    """
    Récupère les fonctionnalités d'un plan.
    
    Args:
        plan: Plan d'abonnement
        
    Returns:
        List[str]: Liste des fonctionnalités
    """
    plan_data = get_plan(plan)
    return plan_data.get("features", []) if plan_data else []


def get_plan_limits(plan: PlanAbonnement) -> Dict:
    """
    Récupère les limites d'un plan.
    
    Args:
        plan: Plan d'abonnement
        
    Returns:
        Dict: Limites du plan
    """
    plan_data = get_plan(plan)
    return plan_data.get("limits", {}) if plan_data else {}


def get_plan_price(plan: PlanAbonnement, annual: bool = False) -> str:
    """
    Récupère le prix d'un plan.
    
    Args:
        plan: Plan d'abonnement
        annual: Prix annuel (défaut: False)
        
    Returns:
        str: Prix formaté
    """
    plan_data = get_plan(plan)
    if not plan_data:
        return ""
    
    key = "prix_annuel" if annual else "prix"
    return plan_data.get(key, plan_data.get("prix", ""))


def get_all_plans() -> List[Dict]:
    """
    Récupère tous les plans sous forme de liste.
    
    Returns:
        List[Dict]: Liste de tous les plans avec leur clé
    """
    return [
        {"plan": plan, **details}
        for plan, details in PLAN_CATALOG.items()
    ]


def get_recommended_plan() -> Optional[PlanAbonnement]:
    """
    Récupère le plan recommandé.
    
    Returns:
        PlanAbonnement: Plan recommandé ou None
    """
    for plan, details in PLAN_CATALOG.items():
        if details.get("recommended", False):
            return plan
    return None


def get_plans_by_price_range(min_price: int, max_price: int) -> List[PlanAbonnement]:
    """
    Récupère les plans dans une fourchette de prix.
    
    Args:
        min_price: Prix minimum
        max_price: Prix maximum
        
    Returns:
        List[PlanAbonnement]: Plans correspondants
    """
    result = []
    for plan, details in PLAN_CATALOG.items():
        prix = details.get("prix", "0")
        # Nettoyer le prix (enlever les espaces)
        prix_clean = prix.replace(" ", "").replace("FCFA", "").strip()
        if prix_clean.isdigit():
            price_value = int(prix_clean)
            if min_price <= price_value <= max_price:
                result.append(plan)
    return result


def compare_plans(plans: List[PlanAbonnement]) -> Dict:
    """
    Compare plusieurs plans.
    
    Args:
        plans: Liste des plans à comparer
        
    Returns:
        Dict: Comparaison des plans
    """
    comparison = {
        "plans": [],
        "features": {},
        "prices": {},
    }
    
    for plan in plans:
        plan_data = get_plan(plan)
        if plan_data:
            comparison["plans"].append({
                "name": plan.value,
                "label": plan_data.get("label"),
                "price": plan_data.get("prix"),
                "recommended": plan_data.get("recommended", False),
            })
            
            # Regrouper les fonctionnalités
            for feature in plan_data.get("features", []):
                if feature not in comparison["features"]:
                    comparison["features"][feature] = []
                comparison["features"][feature].append(plan.value)
            
            comparison["prices"][plan.value] = plan_data.get("prix")
    
    return comparison


# ==========================================================
# Validation
# ==========================================================

def validate_plan(plan: PlanAbonnement) -> bool:
    """
    Valide qu'un plan existe dans le catalogue.
    
    Args:
        plan: Plan à valider
        
    Returns:
        bool: True si le plan existe
    """
    return plan in PLAN_CATALOG


def get_plan_limits_dict(plan: PlanAbonnement) -> Dict:
    """
    Retourne les limites d'un plan sous forme de dictionnaire.
    
    Args:
        plan: Plan d'abonnement
        
    Returns:
        Dict: Limites avec valeurs par défaut
    """
    default_limits = {
        "recruteurs": 0,
        "offres_actives": 0,
        "candidatures_par_offre": 0,
        "stockage_cv": "0 MB",
    }
    
    plan_limits = get_plan_limits(plan)
    return {**default_limits, **plan_limits}