"""Entreprise cliente (tenant). Racine de l'isolation multi-tenant."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.abonnement import Abonnement
    from app.models.campagne import Campagne
    from app.models.utilisateur import Utilisateur


class Entreprise(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "entreprises"

    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    domaine: Mapped[str | None] = mapped_column(String(255), nullable=True)
    secteur: Mapped[str | None] = mapped_column(String(255), nullable=True)
    taille: Mapped[str | None] = mapped_column(String(50), nullable=True)
    adresse: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    utilisateurs: Mapped[list["Utilisateur"]] = relationship(
        back_populates="entreprise", cascade="all, delete-orphan"
    )
    campagnes: Mapped[list["Campagne"]] = relationship(
        back_populates="entreprise", cascade="all, delete-orphan"
    )
    abonnement: Mapped["Abonnement | None"] = relationship(
        back_populates="entreprise", uselist=False, cascade="all, delete-orphan"
    )
