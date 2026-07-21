"""Énumérations métier — miroir exact du contrat frontend (`lib/types` +
`lib/constants`), aligné sur le cahier des charges. Toute évolution doit rester
synchronisée des deux côtés.
"""

from enum import Enum


class RoleUtilisateur(str, Enum):
    """4 rôles internes à une entreprise. Le candidat est une entité à part."""

    recruteur = "recruteur"
    admin_rh = "admin_rh"
    admin_plateforme = "admin_plateforme"
    evaluateur_technique = "evaluateur_technique"


class TypeContrat(str, Enum):
    CDI = "CDI"
    CDD = "CDD"
    Stage = "Stage"
    Alternance = "Alternance"
    Freelance = "Freelance"


class StatutOffre(str, Enum):
    brouillon = "brouillon"
    publiee = "publiee"
    archivee = "archivee"


class StatutCandidature(str, Enum):
    """Pipeline de recrutement (CDC §13). Superset : `decision` conservée."""

    recue = "recue"
    en_cours_analyse = "en_cours_analyse"
    preselectionnee = "preselectionnee"
    test_technique = "test_technique"
    entretien_rh = "entretien_rh"
    entretien_metier = "entretien_metier"
    verification_references = "verification_references"
    decision = "decision"
    offre_envoyee = "offre_envoyee"
    embauche = "embauche"
    refusee = "refusee"
    vivier_talents = "vivier_talents"


class PlanAbonnement(str, Enum):
    starter = "starter"
    business = "business"
    enterprise = "enterprise"


class StatutAbonnement(str, Enum):
    actif = "actif"
    expire = "expire"
    essai = "essai"
