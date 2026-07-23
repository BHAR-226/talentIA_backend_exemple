"""
Schémas Pydantic des candidatures.

Ils définissent :
- les données reçues par l'API
- les données renvoyées au frontend Next.js

Les modèles ORM SQLAlchemy sont convertis grâce à
ConfigDict(from_attributes=True).
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StatutCandidature


# ==========================================================
# Création d'une candidature
# ==========================================================

class CandidatureCreate(BaseModel):
    """
    Données envoyées lors d'une candidature.

    Le CV est envoyé séparément (UploadFile) dans la route FastAPI,
    il n'apparaît donc pas ici.
    """
    
    offre_id: UUID = Field(
        description="ID de l'offre à laquelle le candidat postule"
    )
    lettre_motivation: Optional[str] = Field(
        default=None,
        description="Lettre de motivation du candidat"
    )
    champs_personnalises: dict[str, Any] = Field(
        default_factory=dict,
        description="Réponses aux champs personnalisés de l'offre"
    )


# ==========================================================
# Mise à jour d'une candidature
# ==========================================================

class CandidatureUpdate(BaseModel):
    """
    Mise à jour complète d'une candidature (statut, commentaires, évaluations).
    """
    
    statut: Optional[StatutCandidature] = Field(
        default=None,
        description="Nouveau statut de la candidature"
    )
    commentaires: Optional[str] = Field(
        default=None,
        description="Commentaires sur la candidature"
    )
    evaluation_technique: Optional[dict[str, Any]] = Field(
        default=None,
        description="Évaluation technique du candidat"
    )
    entretien_notes: Optional[dict[str, Any]] = Field(
        default=None,
        description="Notes d'entretien"
    )


class CandidatureUpdateStatut(BaseModel):
    """
    Changement de statut depuis le Kanban recruteur.
    """
    
    statut: StatutCandidature = Field(
        description="Nouveau statut de la candidature"
    )
    commentaires: Optional[str] = Field(
        default=None,
        description="Commentaire optionnel sur le changement de statut"
    )


# ==========================================================
# Mise à jour en masse
# ==========================================================

class CandidatureBulkUpdate(BaseModel):
    """
    Mise à jour en masse du statut de plusieurs candidatures.
    """
    
    candidature_ids: list[UUID] = Field(
        description="Liste des IDs des candidatures à modifier"
    )
    statut: StatutCandidature = Field(
        description="Nouveau statut à appliquer"
    )
    commentaires: Optional[str] = Field(
        default=None,
        description="Commentaire optionnel pour toutes les candidatures"
    )


# ==========================================================
# Filtres de recherche
# ==========================================================

class CandidatureFilters(BaseModel):
    """
    Filtres pour la recherche de candidatures.
    """
    
    offre_id: Optional[UUID] = Field(
        default=None,
        description="Filtrer par offre"
    )
    statut: Optional[StatutCandidature] = Field(
        default=None,
        description="Filtrer par statut"
    )
    date_debut: Optional[datetime] = Field(
        default=None,
        description="Filtrer à partir de cette date"
    )
    date_fin: Optional[datetime] = Field(
        default=None,
        description="Filtrer jusqu'à cette date"
    )
    search: Optional[str] = Field(
        default=None,
        description="Recherche textuelle (nom, email, etc.)"
    )


# ==========================================================
# Réponse API
# ==========================================================

class CandidatureResponse(BaseModel):
    """
    Objet renvoyé au frontend.
    """
    
    model_config = ConfigDict(from_attributes=True)
    
    # Identifiants
    id: UUID = Field(description="ID unique de la candidature")
    offre_id: UUID = Field(description="ID de l'offre associée")
    candidat_id: UUID = Field(description="ID du candidat associé")
    
    # Statut et dates
    statut: StatutCandidature = Field(description="Statut actuel de la candidature")
    date_soumission: datetime = Field(description="Date de soumission de la candidature")
    date_analyse: Optional[datetime] = Field(
        default=None,
        description="Date d'analyse de la candidature"
    )
    decision_date: Optional[datetime] = Field(
        default=None,
        description="Date de décision finale"
    )
    
    # Contenu
    lettre_motivation: Optional[str] = Field(
        default=None,
        description="Lettre de motivation"
    )
    cv_url: Optional[str] = Field(
        default=None,
        description="URL du CV du candidat"
    )
    champs_personnalises: dict[str, Any] = Field(
        default_factory=dict,
        description="Réponses aux champs personnalisés"
    )
    
    # Évaluations
    score_global: Optional[int] = Field(
        default=None,
        description="Score global de la candidature"
    )
    evaluation_ia: Optional[dict[str, Any]] = Field(
        default=None,
        description="Évaluation générée par l'IA"
    )
    evaluation_technique: Optional[dict[str, Any]] = Field(
        default=None,
        description="Évaluation technique manuelle"
    )
    entretien_notes: Optional[dict[str, Any]] = Field(
        default=None,
        description="Notes d'entretien"
    )
    
    # Commentaires et décision
    commentaires: Optional[str] = Field(
        default=None,
        description="Commentaires généraux"
    )
    motif_refus: Optional[str] = Field(
        default=None,
        description="Motif de refus (si applicable)"
    )
    
    # Métadonnées
    created_at: datetime = Field(description="Date de création de l'enregistrement")
    updated_at: datetime = Field(description="Date de dernière modification")
    
    # Relations (optionnelles - pour enrichir les réponses)
    offre_titre: Optional[str] = Field(
        default=None,
        description="Titre de l'offre (enrichissement)"
    )
    candidat_nom: Optional[str] = Field(
        default=None,
        description="Nom du candidat (enrichissement)"
    )
    candidat_email: Optional[str] = Field(
        default=None,
        description="Email du candidat (enrichissement)"
    )