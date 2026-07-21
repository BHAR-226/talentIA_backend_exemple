"""Candidature — entité pivot reliant un candidat à une offre (CDC §8).

`score_global` et `evaluation_ia` restent `null` tant que le matching IA n'a
pas tourné (Lot 5). `champs_personnalises` porte les réponses du candidat aux
champs custom définis sur l'offre.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import StatutCandidature
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.candidat import Candidat
    from app.models.offre import Offre


class Candidature(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "candidatures"

    offre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offres.id", ondelete="CASCADE"), nullable=False
    )
    candidat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidats.id", ondelete="CASCADE"), nullable=False
    )
    statut: Mapped[StatutCandidature] = mapped_column(
        SAEnum(StatutCandidature, name="statut_candidature"),
        default=StatutCandidature.recue,
        nullable=False,
    )
    date_soumission: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    lettre_motivation: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Réponses aux champs personnalisés définis sur l'offre.
    champs_personnalises: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    # Rempli par le matching IA (Lot 5) ; null en attendant.
    score_global: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluation_ia: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    offre: Mapped["Offre"] = relationship(back_populates="candidatures")
    candidat: Mapped["Candidat"] = relationship(back_populates="candidatures")
