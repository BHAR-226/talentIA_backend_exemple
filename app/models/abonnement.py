"""Abonnement SaaS souscrit par une entreprise (un par entreprise)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import PlanAbonnement, StatutAbonnement
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.entreprise import Entreprise


class Abonnement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "abonnements"

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    plan: Mapped[PlanAbonnement] = mapped_column(
        SAEnum(PlanAbonnement, name="plan_abonnement"), nullable=False
    )
    statut: Mapped[StatutAbonnement] = mapped_column(
        SAEnum(StatutAbonnement, name="statut_abonnement"),
        default=StatutAbonnement.essai,
        nullable=False,
    )
    date_debut: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    entreprise: Mapped["Entreprise"] = relationship(back_populates="abonnement")
