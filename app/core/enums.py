"""Énumérations métier — miroir exact du contrat frontend (`lib/types` +
`lib/constants`), aligné sur le cahier des charges. Toute évolution doit rester
synchronisée des deux côtés.
"""

from enum import Enum
from typing import List


# ==========================================================
# Utilisateurs et Rôles
# ==========================================================

class RoleUtilisateur(str, Enum):
    """4 rôles internes à une entreprise. Le candidat est une entité à part."""
    
    recruteur = "recruteur"
    admin_rh = "admin_rh"
    admin_plateforme = "admin_plateforme"
    evaluateur_technique = "evaluateur_technique"
    
    @classmethod
    def get_hierarchy(cls) -> dict:
        """Retourne la hiérarchie des rôles (du plus élevé au plus bas)."""
        return {
            cls.admin_plateforme: 4,
            cls.admin_rh: 3,
            cls.recruteur: 2,
            cls.evaluateur_technique: 1,
        }
    
    def is_superior_to(self, other: "RoleUtilisateur") -> bool:
        """Vérifie si ce rôle est supérieur à un autre."""
        hierarchy = self.get_hierarchy()
        return hierarchy.get(self, 0) > hierarchy.get(other, 0)
    
    def is_equal_to(self, other: "RoleUtilisateur") -> bool:
        """Vérifie si ce rôle est égal à un autre."""
        return self == other
    
    @classmethod
    def get_roles_for_tenant(cls) -> List["RoleUtilisateur"]:
        """Retourne les rôles disponibles pour un tenant (hors admin plateforme)."""
        return [
            cls.admin_rh,
            cls.recruteur,
            cls.evaluateur_technique,
        ]
    
    @classmethod
    def get_management_roles(cls) -> List["RoleUtilisateur"]:
        """Retourne les rôles de gestion (admin RH et admin plateforme)."""
        return [
            cls.admin_rh,
            cls.admin_plateforme,
        ]


# ==========================================================
# Contrats et Offres
# ==========================================================

class TypeContrat(str, Enum):
    """Types de contrats disponibles."""
    
    CDI = "CDI"
    CDD = "CDD"
    Stage = "Stage"
    Alternance = "Alternance"
    Freelance = "Freelance"
    
    @classmethod
    def get_employee_types(cls) -> List["TypeContrat"]:
        """Retourne les types de contrats salariés."""
        return [
            cls.CDI,
            cls.CDD,
        ]
    
    @classmethod
    def get_trainee_types(cls) -> List["TypeContrat"]:
        """Retourne les types de contrats de formation."""
        return [
            cls.Stage,
            cls.Alternance,
        ]
    
    @classmethod
    def get_freelance_types(cls) -> List["TypeContrat"]:
        """Retourne les types de contrats freelances."""
        return [
            cls.Freelance,
        ]


class StatutOffre(str, Enum):
    """Statuts d'une offre d'emploi."""
    
    brouillon = "brouillon"
    publiee = "publiee"
    archivee = "archivee"
    
    @classmethod
    def get_active_statuses(cls) -> List["StatutOffre"]:
        """Retourne les statuts actifs (offres visibles)."""
        return [
            cls.publiee,
        ]
    
    @classmethod
    def get_inactive_statuses(cls) -> List["StatutOffre"]:
        """Retourne les statuts inactifs."""
        return [
            cls.brouillon,
            cls.archivee,
        ]


# ==========================================================
# Candidatures - Pipeline de recrutement
# ==========================================================

class StatutCandidature(str, Enum):
    """Pipeline de recrutement (CDC §13). Superset : `decision` conservée."""
    
    # Étape 1: Réception
    recue = "recue"
    
    # Étape 2: Analyse
    en_cours_analyse = "en_cours_analyse"
    preselectionnee = "preselectionnee"
    
    # Étape 3: Évaluations
    test_technique = "test_technique"
    entretien_rh = "entretien_rh"
    entretien_metier = "entretien_metier"
    verification_references = "verification_references"
    
    # Étape 4: Décision
    decision = "decision"
    offre_envoyee = "offre_envoyee"
    embauche = "embauche"
    refusee = "refusee"
    vivier_talents = "vivier_talents"
    
    @classmethod
    def get_initial_statuses(cls) -> List["StatutCandidature"]:
        """Statuts initiaux (candidature reçue)."""
        return [
            cls.recue,
        ]
    
    @classmethod
    def get_analysis_statuses(cls) -> List["StatutCandidature"]:
        """Statuts d'analyse."""
        return [
            cls.en_cours_analyse,
            cls.preselectionnee,
        ]
    
    @classmethod
    def get_evaluation_statuses(cls) -> List["StatutCandidature"]:
        """Statuts d'évaluation."""
        return [
            cls.test_technique,
            cls.entretien_rh,
            cls.entretien_metier,
            cls.verification_references,
        ]
    
    @classmethod
    def get_decision_statuses(cls) -> List["StatutCandidature"]:
        """Statuts de décision."""
        return [
            cls.decision,
            cls.offre_envoyee,
            cls.embauche,
            cls.refusee,
            cls.vivier_talents,
        ]
    
    @classmethod
    def get_positive_statuses(cls) -> List["StatutCandidature"]:
        """Statuts positifs (avancement dans le pipeline)."""
        return [
            cls.preselectionnee,
            cls.test_technique,
            cls.entretien_rh,
            cls.entretien_metier,
            cls.verification_references,
            cls.decision,
            cls.offre_envoyee,
            cls.embauche,
        ]
    
    @classmethod
    def get_final_statuses(cls) -> List["StatutCandidature"]:
        """Statuts finaux (terminaison du pipeline)."""
        return [
            cls.embauche,
            cls.refusee,
            cls.vivier_talents,
        ]
    
    def is_positive(self) -> bool:
        """Vérifie si le statut est positif."""
        return self in self.get_positive_statuses()
    
    def is_final(self) -> bool:
        """Vérifie si le statut est final."""
        return self in self.get_final_statuses()


# ==========================================================
# Entreprise
# ==========================================================

class StatutEntreprise(str, Enum):
    """Statut du tenant. Une entreprise suspendue perd tout accès (login
    bloqué pour ses membres), sans perte de données — réversible.
    """
    
    active = "active"
    suspendue = "suspendue"
    
    @classmethod
    def get_active_statuses(cls) -> List["StatutEntreprise"]:
        """Retourne les statuts actifs."""
        return [
            cls.active,
        ]
    
    @classmethod
    def get_inactive_statuses(cls) -> List["StatutEntreprise"]:
        """Retourne les statuts inactifs."""
        return [
            cls.suspendue,
        ]


# ==========================================================
# Abonnements
# ==========================================================

class PlanAbonnement(str, Enum):
    """Plans d'abonnement disponibles."""
    
    starter = "starter"
    business = "business"
    enterprise = "enterprise"
    
    @classmethod
    def get_features(cls, plan: "PlanAbonnement") -> dict:
        """Retourne les fonctionnalités d'un plan."""
        from app.core.plans import PLAN_CATALOG
        return PLAN_CATALOG.get(plan, {})
    
    @classmethod
    def get_plans_with_ai(cls) -> List["PlanAbonnement"]:
        """Retourne les plans avec fonctionnalités IA."""
        return [
            cls.business,
            cls.enterprise,
        ]


class StatutAbonnement(str, Enum):
    """Statuts d'un abonnement."""
    
    actif = "actif"
    expire = "expire"
    essai = "essai"
    
    @classmethod
    def get_active_statuses(cls) -> List["StatutAbonnement"]:
        """Retourne les statuts actifs (accès autorisé)."""
        return [
            cls.actif,
            cls.essai,
        ]
    
    @classmethod
    def get_inactive_statuses(cls) -> List["StatutAbonnement"]:
        """Retourne les statuts inactifs (accès bloqué)."""
        return [
            cls.expire,
        ]


# ==========================================================
# Fonctions utilitaires
# ==========================================================

def get_all_enums() -> dict:
    """Retourne toutes les énumérations pour l'export ou la documentation."""
    return {
        "RoleUtilisateur": RoleUtilisateur,
        "TypeContrat": TypeContrat,
        "StatutOffre": StatutOffre,
        "StatutCandidature": StatutCandidature,
        "StatutEntreprise": StatutEntreprise,
        "PlanAbonnement": PlanAbonnement,
        "StatutAbonnement": StatutAbonnement,
    }


def get_enum_choices(enum_class: Enum) -> List[dict]:
    """
    Retourne les choix d'une énumération sous forme de liste de dicts.
    
    Exemple:
        get_enum_choices(RoleUtilisateur)
        # [{"value": "recruteur", "label": "Recruteur"}, ...]
    
    Args:
        enum_class: Classe d'énumération
        
    Returns:
        Liste des choix avec value et label
    """
    return [
        {"value": item.value, "label": item.name.replace("_", " ").title()}
        for item in enum_class
    ]


def get_enum_labels(enum_class: Enum) -> dict:
    """
    Retourne un mapping valeur -> label pour une énumération.
    
    Args:
        enum_class: Classe d'énumération
        
    Returns:
        Dictionnaire {valeur: label}
    """
    return {
        item.value: item.name.replace("_", " ").title()
        for item in enum_class
    }