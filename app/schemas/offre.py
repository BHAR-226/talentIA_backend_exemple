"""Schémas Pydantic pour la gestion des Offres d'emploi (CDC §7)."""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import StatutOffre, TypeContrat


class OffreBase(BaseModel):
    """Champs de base partagés par la création et l'affichage d'une offre."""
    
    titre: str = Field(
        min_length=1,
        max_length=255,
        description="Titre de l'offre d'emploi"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description détaillée du poste et des missions"
    )
    type_contrat: Optional[TypeContrat] = Field(
        default=None,
        description="Type de contrat (CDI, CDD, Stage...)"
    )
    localisation: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Lieu de travail"
    )
    salaire_min: Optional[int] = Field(
        default=None,
        ge=0,
        description="Salaire minimum proposé"
    )
    salaire_max: Optional[int] = Field(
        default=None,
        ge=0,
        description="Salaire maximum proposé"
    )
    
    # Gestion des candidatures
    reception_ouverte: bool = Field(
        default=True,
        description="Indique si l'offre accepte encore des candidatures"
    )
    
    # Champs personnalisables
    champs_personnalises_def: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Questions/champs personnalisés pour le formulaire de candidature"
    )
    
    # Champs additionnels
    missions: List[str] = Field(
        default_factory=list,
        description="Liste des missions principales"
    )
    soft_skills: List[str] = Field(
        default_factory=list,
        description="Compétences comportementales requises"
    )
    avantages: List[str] = Field(
        default_factory=list,
        description="Avantages proposés"
    )
    tele_travail: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Télétravail : full, partial, no"
    )
    visible: bool = Field(
        default=True,
        description="Indique si l'offre est visible publiquement"
    )
    
    @field_validator('salaire_min', 'salaire_max')
    @classmethod
    def validate_salaire(cls, v: Optional[int]) -> Optional[int]:
        """Valide que le salaire est positif."""
        if v is not None and v < 0:
            raise ValueError('Le salaire doit être positif')
        return v
    
    @field_validator('salaire_min', 'salaire_max')
    @classmethod
    def validate_salaire_range(cls, v: Optional[int], info) -> Optional[int]:
        """Valide que le salaire min est inférieur au salaire max."""
        if 'salaire_min' in info.data and 'salaire_max' in info.data:
            min_val = info.data.get('salaire_min')
            max_val = info.data.get('salaire_max')
            if min_val is not None and max_val is not None and min_val > max_val:
                raise ValueError('Le salaire minimum doit être inférieur au maximum')
        return v


class OffreCreate(OffreBase):
    """Schéma pour la création d'une offre via POST.
    L'offre est liée à une campagne spécifique.
    """
    
    campagne_id: uuid.UUID = Field(
        description="ID de la campagne associée"
    )
    statut: StatutOffre = Field(
        default=StatutOffre.brouillon,
        description="Statut initial de l'offre"
    )


class OffreUpdate(BaseModel):
    """Schéma pour la mise à jour partielle d'une offre (PUT/PATCH)."""
    
    titre: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255
    )
    description: Optional[str] = Field(
        default=None
    )
    type_contrat: Optional[TypeContrat] = Field(
        default=None
    )
    localisation: Optional[str] = Field(
        default=None,
        max_length=255
    )
    salaire_min: Optional[int] = Field(
        default=None,
        ge=0
    )
    salaire_max: Optional[int] = Field(
        default=None,
        ge=0
    )
    statut: Optional[StatutOffre] = Field(
        default=None
    )
    reception_ouverte: Optional[bool] = Field(
        default=None
    )
    champs_personnalises_def: Optional[List[dict[str, Any]]] = Field(
        default=None
    )
    missions: Optional[List[str]] = Field(
        default=None
    )
    soft_skills: Optional[List[str]] = Field(
        default=None
    )
    avantages: Optional[List[str]] = Field(
        default=None
    )
    tele_travail: Optional[str] = Field(
        default=None,
        max_length=50
    )
    visible: Optional[bool] = Field(
        default=None
    )
    
    @field_validator('salaire_min', 'salaire_max')
    @classmethod
    def validate_salaire(cls, v: Optional[int]) -> Optional[int]:
        """Valide que le salaire est positif."""
        if v is not None and v < 0:
            raise ValueError('Le salaire doit être positif')
        return v
    
    @field_validator('salaire_min', 'salaire_max')
    @classmethod
    def validate_salaire_range(cls, v: Optional[int], info) -> Optional[int]:
        """Valide que le salaire min est inférieur au salaire max."""
        if 'salaire_min' in info.data and 'salaire_max' in info.data:
            min_val = info.data.get('salaire_min')
            max_val = info.data.get('salaire_max')
            if min_val is not None and max_val is not None and min_val > max_val:
                raise ValueError('Le salaire minimum doit être inférieur au maximum')
        return v


class OffreReceptionUpdate(BaseModel):
    """Schéma spécifique pour l'action du bouton 'Arrêter/Rouvrir' les candidatures."""
    
    reception_ouverte: bool = Field(
        description="True pour ouvrir, False pour arrêter la réception"
    )


class OffreResponse(OffreBase):
    """Schéma renvoyé au Frontend lors de la lecture d'une offre (GET)."""
    
    model_config = ConfigDict(from_attributes=True)
    
    # Identifiants
    id: uuid.UUID = Field(description="ID unique de l'offre")
    campagne_id: uuid.UUID = Field(description="ID de la campagne associée")
    createur_id: Optional[uuid.UUID] = Field(
        default=None,
        description="ID de l'utilisateur qui a créé l'offre"
    )
    
    # Statut et dates
    statut: StatutOffre = Field(description="Statut actuel de l'offre")
    date_publication: Optional[datetime] = Field(
        default=None,
        description="Date de publication de l'offre"
    )
    created_at: datetime = Field(description="Date de création")
    updated_at: datetime = Field(description="Date de dernière modification")
    
    # Métriques calculées
    nombre_candidatures: int = Field(
        default=0,
        description="Nombre total de candidatures reçues"
    )
    est_publiee: bool = Field(
        default=False,
        description="Indique si l'offre est publiée"
    )
    est_archivee: bool = Field(
        default=False,
        description="Indique si l'offre est archivée"
    )
    est_pourvue: bool = Field(
        default=False,
        description="Indique si le poste est pourvu"
    )