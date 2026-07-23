"""Schémas Pydantic pour la gestion des Campagnes (CDC §6)."""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import TypeContrat


class CampagneBase(BaseModel):
    """Champs communs à la création et à l'affichage d'une campagne."""
    
    intitule: str = Field(
        min_length=1,
        max_length=255,
        description="Intitulé de la campagne"
    )
    departement: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Département ou service concerné"
    )
    date_limite: Optional[datetime] = Field(
        default=None,
        description="Date limite de la campagne"
    )
    nombre_postes: int = Field(
        default=1,
        ge=1,
        le=1000,
        description="Nombre de postes à pourvoir"
    )
    
    # Critères de cadrage de la campagne
    localisation: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Localisation du poste"
    )
    competences: List[str] = Field(
        default_factory=list,
        description="Compétences requises"
    )
    experience_requise: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Expérience requise (ex: 3-5 ans)"
    )
    langues: List[str] = Field(
        default_factory=list,
        description="Langues requises"
    )
    niveau_etudes: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Niveau d'études requis"
    )
    type_contrat: Optional[TypeContrat] = Field(
        default=None,
        description="Type de contrat proposé"
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
    
    # Gestion de la campagne
    recruteurs_responsables: List[uuid.UUID] = Field(
        default_factory=list,
        description="Liste des IDs des recruteurs responsables"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description détaillée de la campagne"
    )
    workflow: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Workflow personnalisé de la campagne"
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


class CampagneCreate(CampagneBase):
    """Schéma pour la création d'une campagne via POST."""
    pass


class CampagneUpdate(BaseModel):
    """Schéma pour la mise à jour partielle via PUT/PATCH.
    Tous les champs sont optionnels pour ne modifier que ce qui est transmis.
    """
    
    intitule: Optional[str] = Field(None, min_length=1, max_length=255)
    departement: Optional[str] = Field(None, max_length=255)
    date_limite: Optional[datetime] = None
    nombre_postes: Optional[int] = Field(None, ge=1, le=1000)
    localisation: Optional[str] = Field(None, max_length=255)
    competences: Optional[List[str]] = None
    experience_requise: Optional[str] = Field(None, max_length=100)
    langues: Optional[List[str]] = None
    niveau_etudes: Optional[str] = Field(None, max_length=100)
    type_contrat: Optional[TypeContrat] = None
    salaire_min: Optional[int] = Field(None, ge=0)
    salaire_max: Optional[int] = Field(None, ge=0)
    recruteurs_responsables: Optional[List[uuid.UUID]] = None
    description: Optional[str] = None
    statut: Optional[str] = Field(
        default=None,
        description="Statut de la campagne (active, terminee, annulee)"
    )
    workflow: Optional[List[dict[str, Any]]] = None
    
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


class CampagneResponse(CampagneBase):
    """Schéma renvoyé au Frontend lors de la lecture d'une campagne (GET)."""
    
    id: uuid.UUID = Field(description="Identifiant unique de la campagne")
    entreprise_id: uuid.UUID = Field(description="ID de l'entreprise propriétaire")
    statut: str = Field(
        default="active",
        description="Statut de la campagne"
    )
    created_at: datetime = Field(description="Date de création")
    updated_at: datetime = Field(description="Date de dernière modification")
    
    # Propriétés calculées
    nombre_offres: int = Field(
        default=0,
        description="Nombre d'offres associées à la campagne"
    )
    est_terminee: bool = Field(
        default=False,
        description="Indique si la campagne est terminée"
    )
    nombre_postes_pourvus: int = Field(
        default=0,
        description="Nombre de postes pourvus"
    )
    
    model_config = ConfigDict(from_attributes=True)