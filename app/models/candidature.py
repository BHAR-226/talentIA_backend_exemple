"""Candidature — entité pivot reliant un candidat à une offre (CDC §8).

`score_global` et `evaluation_ia` restent `null` tant que le matching IA n'a
pas tourné (Lot 5). `champs_personnalises` porte les réponses du candidat aux
champs custom définis sur l'offre.
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import StatutCandidature
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.candidat import Candidat
    from app.models.offre import Offre


class Candidature(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Modèle représentant une candidature à une offre d'emploi.
    
    Une candidature est créée lorsqu'un candidat postule à une offre.
    Elle suit un pipeline de statuts définis par StatutCandidature.
    """
    
    __tablename__ = "candidatures"
    __table_args__ = (
        Index("ix_candidatures_offre_id", "offre_id"),
        Index("ix_candidatures_candidat_id", "candidat_id"),
        Index("ix_candidatures_statut", "statut"),
        Index("ix_candidatures_date_soumission", "date_soumission"),
    )

    # ==========================================================
    # Relations
    # ==========================================================
    
    offre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("offres.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID de l'offre associée"
    )
    
    candidat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidats.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID du candidat associé"
    )
    
    # ==========================================================
    # Statut et dates
    # ==========================================================
    
    statut: Mapped[StatutCandidature] = mapped_column(
        SAEnum(StatutCandidature, name="statut_candidature"),
        default=StatutCandidature.recue,
        nullable=False,
        comment="Statut actuel de la candidature"
    )
    
    date_soumission: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Date et heure de soumission"
    )
    
    # ==========================================================
    # Contenu de la candidature
    # ==========================================================
    
    lettre_motivation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Lettre de motivation du candidat"
    )
    
    cv_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="URL du CV du candidat"
    )
    
    # Réponses aux champs personnalisés définis sur l'offre
    champs_personnalises: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Réponses aux champs personnalisés"
    )
    
    # ==========================================================
    # Évaluation IA (Lot 5)
    # ==========================================================
    
    score_global: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Score global calculé par l'IA (0-100)"
    )
    
    evaluation_ia: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Évaluation détaillée générée par l'IA"
    )
    
    # ==========================================================
    # Suivi du pipeline
    # ==========================================================
    
    date_analyse: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date d'analyse de la candidature"
    )
    
    commentaires: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Commentaires généraux sur la candidature"
    )
    
    evaluation_technique: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Évaluation technique du candidat"
    )
    
    entretien_notes: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Notes d'entretien"
    )
    
    # ==========================================================
    # Décision finale
    # ==========================================================
    
    decision_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date de la décision finale"
    )
    
    motif_refus: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Motif du refus (si applicable)"
    )

    # ==========================================================
    # Relations
    # ==========================================================
    
    offre: Mapped["Offre"] = relationship(
        back_populates="candidatures",
        lazy="selectin"
    )
    
    candidat: Mapped["Candidat"] = relationship(
        back_populates="candidatures",
        lazy="selectin"
    )
    
    # ==========================================================
    # Propriétés calculées
    # ==========================================================
    
    @property
    def est_recue(self) -> bool:
        """Indique si la candidature est à l'état 'reçue'."""
        return self.statut == StatutCandidature.recue
    
    @property
    def est_en_analyse(self) -> bool:
        """Indique si la candidature est en cours d'analyse."""
        return self.statut == StatutCandidature.en_cours_analyse
    
    @property
    def est_presélectionnee(self) -> bool:
        """Indique si la candidature est présélectionnée."""
        return self.statut == StatutCandidature.preselectionnee
    
    @property
    def est_acceptee(self) -> bool:
        """Indique si la candidature est acceptée (statuts positifs)."""
        return self.statut in (
            StatutCandidature.preselectionnee,
            StatutCandidature.test_technique,
            StatutCandidature.entretien_rh,
            StatutCandidature.entretien_metier,
            StatutCandidature.verification_references,
            StatutCandidature.decision,
            StatutCandidature.offre_envoyee,
            StatutCandidature.embauche,
        )
    
    @property
    def est_refusee(self) -> bool:
        """Indique si la candidature est refusée."""
        return self.statut == StatutCandidature.refusee
    
    @property
    def est_embauchee(self) -> bool:
        """Indique si le candidat a été embauché."""
        return self.statut == StatutCandidature.embauche
    
    @property
    def est_en_vivier(self) -> bool:
        """Indique si la candidature est en vivier de talents."""
        return self.statut == StatutCandidature.vivier_talents
    
    @property
    def a_decision(self) -> bool:
        """Indique si une décision a été prise."""
        return self.decision_date is not None
    
    @property
    def temps_analyse(self) -> Optional[int]:
        """Nombre de jours entre la soumission et l'analyse."""
        if self.date_analyse and self.date_soumission:
            delta = self.date_analyse - self.date_soumission
            return delta.days
        return None
    
    # ==========================================================
    # Méthodes
    # ==========================================================
    
    def changer_statut(self, nouveau_statut: StatutCandidature, commentaire: Optional[str] = None) -> None:
        """Change le statut de la candidature.
        
        Args:
            nouveau_statut: Nouveau statut à appliquer
            commentaire: Commentaire optionnel sur le changement
        """
        self.statut = nouveau_statut
        
        if commentaire:
            self.commentaires = commentaire
        
        # Mettre à jour les dates selon le statut
        if nouveau_statut == StatutCandidature.en_cours_analyse and not self.date_analyse:
            self.date_analyse = datetime.now(UTC)
        
        if nouveau_statut in (StatutCandidature.refusee, StatutCandidature.embauche):
            self.decision_date = datetime.now(UTC)
    
    def analyser(self) -> None:
        """Marque la candidature comme 'en cours d'analyse'."""
        self.changer_statut(StatutCandidature.en_cours_analyse)
    
    def presélectionner(self, commentaire: Optional[str] = None) -> None:
        """Présélectionne la candidature."""
        self.changer_statut(StatutCandidature.preselectionnee, commentaire)
    
    def refuser(self, motif: str, commentaire: Optional[str] = None) -> None:
        """Refuse la candidature avec un motif."""
        self.motif_refus = motif
        self.changer_statut(StatutCandidature.refusee, commentaire)
    
    def embaucher(self, commentaire: Optional[str] = None) -> None:
        """Valide l'embauche du candidat."""
        self.changer_statut(StatutCandidature.embauche, commentaire)
    
    def mettre_en_vivier(self, commentaire: Optional[str] = None) -> None:
        """Place la candidature en vivier de talents."""
        self.changer_statut(StatutCandidature.vivier_talents, commentaire)
    
    def envoyer_offre(self, commentaire: Optional[str] = None) -> None:
        """Marque l'offre comme envoyée."""
        self.changer_statut(StatutCandidature.offre_envoyee, commentaire)
    
    def update_evaluation_ia(self, score: int, evaluation: dict[str, Any]) -> None:
        """Met à jour l'évaluation IA de la candidature.
        
        Args:
            score: Score global (0-100)
            evaluation: Détails de l'évaluation
        """
        self.score_global = score
        self.evaluation_ia = evaluation
    
    def __repr__(self) -> str:
        """Représentation lisible de la candidature."""
        return (
            f"<Candidature id={self.id} "
            f"offre_id={self.offre_id} "
            f"candidat_id={self.candidat_id} "
            f"statut={self.statut.value}>"
        )