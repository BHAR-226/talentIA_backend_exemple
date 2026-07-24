"""Offre d'emploi publiée dans le cadre d'une campagne (CDC §7)."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import StatutCandidature, StatutOffre, TypeContrat
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.campagne import Campagne
    from app.models.candidature import Candidature


class Offre(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Modèle représentant une offre d'emploi publiée dans une campagne.
    
    Une offre est liée à une campagne et peut avoir plusieurs candidatures.
    Elle définit les critères du poste et les champs personnalisés pour
    le formulaire de candidature.
    """

    __tablename__ = "offres"
    __table_args__ = (
        Index("ix_offres_campagne_id", "campagne_id"),
        Index("ix_offres_statut", "statut"),
        Index("ix_offres_date_publication", "date_publication"),
        Index(
            "ix_offres_search",
            text(
                "to_tsvector('french', coalesce(titre, '') || ' ' || coalesce(description, ''))"
            ),
            postgresql_using='gin'
        ),
    )

    # ==========================================================
    # Relations
    # ==========================================================

    campagne_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campagnes.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID de la campagne associée"
    )

    createur_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("utilisateurs.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID de l'utilisateur créateur"
    )

    # ==========================================================
    # Informations générales
    # ==========================================================

    titre: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Titre de l'offre d'emploi"
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description détaillée du poste"
    )

    type_contrat: Mapped[TypeContrat | None] = mapped_column(
        SAEnum(TypeContrat, name="type_contrat"),
        nullable=True,
        comment="Type de contrat proposé"
    )

    localisation: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Lieu de travail"
    )

    salaire_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Salaire minimum proposé"
    )

    salaire_max: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Salaire maximum proposé"
    )

    # ==========================================================
    # Statut et dates
    # ==========================================================

    statut: Mapped[StatutOffre] = mapped_column(
        SAEnum(StatutOffre, name="statut_offre"),
        default=StatutOffre.brouillon,
        nullable=False,
        comment="Statut de l'offre (brouillon, publiée, archivée)"
    )

    date_publication: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date de publication de l'offre"
    )

    # ==========================================================
    # Gestion des candidatures
    # ==========================================================

    reception_ouverte: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Indique si l'offre accepte encore des candidatures"
    )

    # ==========================================================
    # Champs personnalisables
    # ==========================================================

    champs_personnalises_def: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Définition des champs personnalisés pour le formulaire"
    )

    # ==========================================================
    # Champs additionnels
    # ==========================================================

    missions: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Liste des missions principales"
    )

    soft_skills: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Compétences comportementales requises"
    )

    avantages: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="Avantages proposés"
    )

    tele_travail: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Télétravail : full, partial, no"
    )

    visible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Indique si l'offre est visible publiquement"
    )

    # ==========================================================
    # Relations
    # ==========================================================

    campagne: Mapped["Campagne"] = relationship(
        back_populates="offres",
        lazy="selectin"
    )

    candidatures: Mapped[list["Candidature"]] = relationship(
        back_populates="offre",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # ==========================================================
    # Propriétés calculées
    # ==========================================================

    @property
    def nombre_candidatures(self) -> int:
        """Nombre total de candidatures reçues."""
        return len(self.candidatures)

    @property
    def est_publiee(self) -> bool:
        """Indique si l'offre est publiée."""
        return self.statut == StatutOffre.publiee

    @property
    def est_archivee(self) -> bool:
        """Indique si l'offre est archivée."""
        return self.statut == StatutOffre.archivee

    @property
    def est_brouillon(self) -> bool:
        """Indique si l'offre est en brouillon."""
        return self.statut == StatutOffre.brouillon

    @property
    def est_pourvue(self) -> bool:
        """Indique si le poste est pourvu (au moins un candidat embauché)."""
        return any(c.statut == StatutCandidature.embauche for c in self.candidatures)

    @property
    def est_visible(self) -> bool:
        """Indique si l'offre est visible (publiée et visible)."""
        return self.est_publiee and self.visible

    @property
    def est_ouverte(self) -> bool:
        """Indique si l'offre accepte des candidatures."""
        return self.est_publiee and self.reception_ouverte

    @property
    def nombre_candidatures_recues(self) -> int:
        """Nombre de candidatures reçues (statut 'recue')."""
        return sum(1 for c in self.candidatures if c.est_recue)

    @property
    def nombre_candidatures_analysees(self) -> int:
        """Nombre de candidatures analysées."""
        return sum(1 for c in self.candidatures if not c.est_recue and not c.est_refusee)

    @property
    def taux_conversion(self) -> float:
        """Taux de conversion (candidatures analysées / total)."""
        if self.nombre_candidatures == 0:
            return 0.0
        return (self.nombre_candidatures_analysees / self.nombre_candidatures) * 100

    @property
    def fourchette_salaire(self) -> str | None:
        """Retourne la fourchette de salaire formatée."""
        if self.salaire_min and self.salaire_max:
            return f"{self.salaire_min} - {self.salaire_max} €"
        if self.salaire_min:
            return f"À partir de {self.salaire_min} €"
        if self.salaire_max:
            return f"Jusqu'à {self.salaire_max} €"
        return None

    # ==========================================================
    # Méthodes
    # ==========================================================

    def publier(self) -> None:
        """Publie l'offre et l'ouvre aux candidatures."""
        self.statut = StatutOffre.publiee
        self.date_publication = datetime.now(UTC)
        self.reception_ouverte = True

    def archiver(self) -> None:
        """Archive l'offre et ferme les candidatures."""
        self.statut = StatutOffre.archivee
        self.reception_ouverte = False

    def arreter_reception(self) -> None:
        """Arrête la réception des candidatures (bouton 'Arrêter')."""
        self.reception_ouverte = False

    def rouvrir_reception(self) -> None:
        """Rouvre la réception des candidatures (bouton 'Rouvrir')."""
        if self.est_publiee:
            self.reception_ouverte = True

    def dupliquer(self) -> "Offre":
        """Crée une copie de l'offre en brouillon.
        
        Returns:
            Offre: Nouvelle offre en brouillon
        """
        from copy import deepcopy

        return Offre(
            campagne_id=self.campagne_id,
            createur_id=self.createur_id,
            titre=f"{self.titre} (copie)",
            description=self.description,
            type_contrat=self.type_contrat,
            localisation=self.localisation,
            salaire_min=self.salaire_min,
            salaire_max=self.salaire_max,
            statut=StatutOffre.brouillon,
            champs_personnalises_def=deepcopy(self.champs_personnalises_def),
            missions=self.missions.copy(),
            soft_skills=self.soft_skills.copy(),
            avantages=self.avantages.copy(),
            tele_travail=self.tele_travail,
            visible=self.visible,
        )

    def __repr__(self) -> str:
        """Représentation lisible de l'offre."""
        return (
            f"<Offre id={self.id} "
            f"titre={self.titre} "
            f"statut={self.statut.value} "
            f"candidatures={self.nombre_candidatures}>"
        )
