"""Utilisateur interne d'une entreprise (recruteur / admin RH / admin
plateforme / évaluateur technique). Le candidat est une entité distincte."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import RoleUtilisateur
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.entreprise import Entreprise


class Utilisateur(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "utilisateurs"

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entreprises.id", ondelete="CASCADE"), nullable=False
    )
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleUtilisateur] = mapped_column(
        SAEnum(RoleUtilisateur, name="role_utilisateur"), nullable=False
    )
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    entreprise: Mapped["Entreprise"] = relationship(back_populates="utilisateurs")
