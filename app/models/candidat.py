"""Candidat — indépendant de toute entreprise (peut postuler partout). Le
parsing du CV et l'enrichissement IA seront ajoutés au Lot 5."""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.candidature import Candidature


class Candidat(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "candidats"

    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Nullable : un candidat peut exister sans compte (créé lors d'une candidature
    # sans inscription) ; renseigné à l'inscription pour permettre la connexion.
    mot_de_passe_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    titre_principal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    annees_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    localisation: Mapped[str | None] = mapped_column(String(255), nullable=True)

    candidatures: Mapped[list["Candidature"]] = relationship(back_populates="candidat")
