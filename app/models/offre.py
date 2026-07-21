"""Offre d'emploi publiée dans le cadre d'une campagne (CDC §7)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import StatutOffre, TypeContrat
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.campagne import Campagne
    from app.models.candidature import Candidature


class Offre(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "offres"

    campagne_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campagnes.id", ondelete="CASCADE"), nullable=False
    )
    createur_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True
    )
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_contrat: Mapped[TypeContrat | None] = mapped_column(
        SAEnum(TypeContrat, name="type_contrat"), nullable=True
    )
    localisation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    salaire_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salaire_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    statut: Mapped[StatutOffre] = mapped_column(
        SAEnum(StatutOffre, name="statut_offre"),
        default=StatutOffre.brouillon,
        nullable=False,
    )
    date_publication: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Réception des candidatures : coupée manuellement via le bouton « Arrêter ».
    reception_ouverte: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Champs personnalisables (au-delà de CV + lettre de motivation) : liste de
    # définitions {libelle, type, obligatoire, ...} configurée par le recruteur.
    champs_personnalises_def: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )

    campagne: Mapped["Campagne"] = relationship(back_populates="offres")
    candidatures: Mapped[list["Candidature"]] = relationship(
        back_populates="offre", cascade="all, delete-orphan"
    )
