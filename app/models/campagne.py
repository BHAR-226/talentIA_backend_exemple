"""Campagne de recrutement : regroupe une ou plusieurs offres (CDC §6)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.entreprise import Entreprise
    from app.models.offre import Offre


class Campagne(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "campagnes"

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False
    )
    intitule: Mapped[str] = mapped_column(String(255), nullable=False)
    departement: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_limite: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nombre_postes: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    entreprise: Mapped["Entreprise"] = relationship(back_populates="campagnes")
    offres: Mapped[list["Offre"]] = relationship(
        back_populates="campagne", cascade="all, delete-orphan"
    )
