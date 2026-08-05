"""Abonnement SaaS souscrit par une entreprise (un par entreprise)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import PlanAbonnement, StatutAbonnement
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.entreprise import Entreprise


class Abonnement(UUIDMixin, TimestampMixin, Base):
    """Modèle représentant l'abonnement SaaS d'une entreprise.

    Un abonnement est associé à une seule entreprise et définit son plan,
    son statut et ses dates de validité.
    """

    __tablename__ = "abonnements"
    __table_args__ = (
        CheckConstraint('date_debut <= date_fin', name='check_dates_abonnement'),
        CheckConstraint(
            "statut IN ('actif', 'expire', 'essai')",
            name='check_statut_abonnement'
        ),
    )

    # ==========================================================
    # Relations
    # ==========================================================

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="ID de l'entreprise propriétaire de l'abonnement"
    )

    # ==========================================================
    # Informations de l'abonnement
    # ==========================================================

    plan: Mapped[PlanAbonnement] = mapped_column(
        SAEnum(PlanAbonnement, name="plan_abonnement"),
        nullable=False,
        comment="Plan d'abonnement (starter, business, enterprise)"
    )

    statut: Mapped[StatutAbonnement] = mapped_column(
        SAEnum(StatutAbonnement, name="statut_abonnement"),
        default=StatutAbonnement.essai,
        nullable=False,
        comment="Statut de l'abonnement (actif, expire, essai)"
    )

    # ==========================================================
    # Dates
    # ==========================================================

    date_debut: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Date de début de l'abonnement"
    )

    date_fin: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Date de fin de l'abonnement"
    )

    # ==========================================================
    # Renouvellement
    # ==========================================================

    renouvellement_auto: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="Indique si l'abonnement se renouvelle automatiquement"
    )

    derniere_renouvellement: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date du dernier renouvellement"
    )

    # ==========================================================
    # Relations
    # ==========================================================

    entreprise: Mapped["Entreprise"] = relationship(
        back_populates="abonnement",
        lazy="selectin"
    )

    # ==========================================================
    # Propriétés calculées
    # ==========================================================

    @property
    def est_expire(self) -> bool:
        """Vérifie si l'abonnement est expiré."""
        return datetime.now(UTC) > self.date_fin

    @property
    def jours_restants(self) -> int:
        """Nombre de jours restants avant expiration."""
        delta = self.date_fin - datetime.now(UTC)
        return max(0, delta.days)

    @property
    def est_en_essai(self) -> bool:
        """Indique si l'abonnement est en période d'essai."""
        return self.statut == StatutAbonnement.essai

    @property
    def est_actif(self) -> bool:
        """Indique si l'abonnement est actif."""
        return self.statut == StatutAbonnement.actif and not self.est_expire

    # ==========================================================
    # Méthodes
    # ==========================================================

    def renouveler(self, duree_jours: int = 30) -> None:
        """Renouvelle l'abonnement pour une durée donnée.

        Args:
            duree_jours: Nombre de jours de renouvellement (défaut: 30)
        """
        maintenant = datetime.now(UTC)
        self.date_debut = maintenant
        self.date_fin = maintenant + timedelta(days=duree_jours)
        self.statut = StatutAbonnement.actif
        self.derniere_renouvellement = maintenant

    def prolonger(self, duree_jours: int = 30) -> None:
        """Prolonge l'abonnement existant d'une durée donnée.

        Args:
            duree_jours: Nombre de jours à ajouter
        """
        if self.date_fin < datetime.now(UTC):
            # Si expiré, on repart de maintenant
            self.date_debut = datetime.now(UTC)
            self.date_fin = self.date_debut + timedelta(days=duree_jours)
        else:
            # Sinon, on prolonge depuis la date de fin actuelle
            self.date_fin = self.date_fin + timedelta(days=duree_jours)

        self.statut = StatutAbonnement.actif
        self.derniere_renouvellement = datetime.now(UTC)

    def mettre_en_essai(self, duree_jours: int = 30) -> None:
        """Met l'abonnement en période d'essai.

        Args:
            duree_jours: Durée de l'essai en jours
        """
        maintenant = datetime.now(UTC)
        self.date_debut = maintenant
        self.date_fin = maintenant + timedelta(days=duree_jours)
        self.statut = StatutAbonnement.essai
        self.renouvellement_auto = False
        self.derniere_renouvellement = None

    def annuler(self) -> None:
        """Annule l'abonnement (le passe en expiré)."""
        self.statut = StatutAbonnement.expire
        self.renouvellement_auto = False

    def __repr__(self) -> str:
        """Représentation lisible de l'abonnement."""
        return (
            f"<Abonnement id={self.id} "
            f"entreprise_id={self.entreprise_id} "
            f"plan={self.plan.value} "
            f"statut={self.statut.value}>"
        )
