"""Campagne de recrutement : regroupe une ou plusieurs offres (CDC §6)."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import TypeContrat
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.entreprise import Entreprise
    from app.models.offre import Offre


class Campagne(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Modèle représentant une campagne de recrutement.
    
    Une campagne regroupe plusieurs offres d'emploi et définit les critères
    généraux de recrutement (localisation, compétences, expérience, etc.).
    """
    
    __tablename__ = "campagnes"
    __table_args__ = (
        Index("ix_campagnes_entreprise_id", "entreprise_id"),
        Index("ix_campagnes_date_limite", "date_limite"),
        Index("ix_campagnes_statut", "statut"),
    )

    # ==========================================================
    # Relations
    # ==========================================================
    
    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID de l'entreprise propriétaire"
    )
    
    # ==========================================================
    # Informations générales
    # ==========================================================
    
    intitule: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Intitulé de la campagne"
    )
    
    departement: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Département ou service concerné"
    )
    
    date_limite: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date limite de la campagne"
    )
    
    nombre_postes: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Nombre de postes à pourvoir"
    )
    
    # ==========================================================
    # Critères de cadrage (CDC §6)
    # ==========================================================
    
    localisation: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Localisation du poste"
    )
    
    competences: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Compétences requises"
    )
    
    experience_requise: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Expérience requise (ex: 3-5 ans)"
    )
    
    langues: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Langues requises"
    )
    
    niveau_etudes: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Niveau d'études requis"
    )
    
    type_contrat: Mapped[Optional[TypeContrat]] = mapped_column(
        SAEnum(TypeContrat, name="type_contrat"),
        nullable=True,
        comment="Type de contrat proposé"
    )
    
    salaire_min: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Salaire minimum proposé"
    )
    
    salaire_max: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Salaire maximum proposé"
    )
    
    # ==========================================================
    # Gestion de la campagne
    # ==========================================================
    
    recruteurs_responsables: Mapped[list[uuid.UUID]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Liste des IDs des recruteurs responsables"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description détaillée de la campagne"
    )
    
    workflow: Mapped[Optional[list[dict]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Workflow personnalisé de la campagne"
    )
    
    statut: Mapped[str] = mapped_column(
        String(50),
        default="active",
        nullable=False,
        comment="Statut de la campagne (active, terminee, annulee)"
    )

    # ==========================================================
    # Relations
    # ==========================================================
    
    entreprise: Mapped["Entreprise"] = relationship(
        back_populates="campagnes",
        lazy="selectin"
    )
    
    offres: Mapped[list["Offre"]] = relationship(
        back_populates="campagne",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Offre.created_at.desc()"
    )
    
    # ==========================================================
    # Propriétés calculées
    # ==========================================================
    
    @property
    def nombre_offres(self) -> int:
        """Nombre d'offres associées à la campagne."""
        return len(self.offres)
    
    @property
    def est_terminee(self) -> bool:
        """Indique si la campagne est terminée (date dépassée)."""
        if self.date_limite:
            return datetime.now(UTC) > self.date_limite
        return False
    
    @property
    def est_active(self) -> bool:
        """Indique si la campagne est active."""
        return self.statut == "active" and not self.est_terminee
    
    @property
    def est_annulee(self) -> bool:
        """Indique si la campagne est annulée."""
        return self.statut == "annulee"
    
    @property
    def nombre_postes_pourvus(self) -> int:
        """Nombre de postes pourvus dans la campagne."""
        return sum(1 for offre in self.offres if offre.est_pourvue)
    
    @property
    def taux_remplissage(self) -> float:
        """Taux de remplissage de la campagne (postes pourvus / postes totaux)."""
        if self.nombre_postes == 0:
            return 0.0
        return (self.nombre_postes_pourvus / self.nombre_postes) * 100
    
    # ==========================================================
    # Méthodes
    # ==========================================================
    
    def terminer(self) -> None:
        """Marque la campagne comme terminée."""
        self.statut = "terminee"
    
    def annuler(self) -> None:
        """Annule la campagne."""
        self.statut = "annulee"
        # Annuler toutes les offres associées
        for offre in self.offres:
            if offre.est_publiee:
                offre.archiver()
    
    def reactiver(self) -> None:
        """Réactive une campagne annulée ou terminée."""
        self.statut = "active"
        self.date_limite = None  # Réinitialiser la date limite
    
    def __repr__(self) -> str:
        """Représentation lisible de la campagne."""
        return (
            f"<Campagne id={self.id} "
            f"intitule={self.intitule} "
            f"statut={self.statut} "
            f"offres={self.nombre_offres}>"
        )