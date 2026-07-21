"""Campagne de recrutement : regroupe une ou plusieurs offres (CDC §6)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
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

    # Nouveaux champs pour cadrer le besoin de la campagne (CDC §6)
    localisation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    competences: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    experience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    langues: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    niveau_etudes: Mapped[str | None] = mapped_column(String(100), nullable=True)
    type_contrat: Mapped[str | None] = mapped_column(String(100), nullable=True)
    salaire: Mapped[str | None] = mapped_column(String(100), nullable=True)
    workflow: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    entreprise: Mapped["Entreprise"] = relationship(back_populates="campagnes")
    offres: Mapped[list["Offre"]] = relationship(
        back_populates="campagne", cascade="all, delete-orphan"
    )
