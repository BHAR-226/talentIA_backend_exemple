"""Entreprise cliente (tenant). Racine de l'isolation multi-tenant."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import StatutEntreprise
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.abonnement import Abonnement
    from app.models.campagne import Campagne
    from app.models.utilisateur import Utilisateur


class Entreprise(UUIDMixin, TimestampMixin, Base):
    """Modèle représentant une entreprise cliente (tenant).
    
    L'entreprise est la racine de l'isolation multi-tenant. Toutes les données
    (utilisateurs, campagnes, offres, candidatures) sont scopées par entreprise.
    """

    __tablename__ = "entreprises"
    __table_args__ = (
        Index("ix_entreprises_nom", "nom"),
        Index("ix_entreprises_statut", "statut"),
    )

    # ==========================================================
    # Informations générales
    # ==========================================================

    nom: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Nom de l'entreprise"
    )

    domaine: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Domaine d'activité"
    )

    secteur: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Secteur d'activité"
    )

    taille: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Taille de l'entreprise (PME, Grand Groupe, etc.)"
    )

    adresse: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Adresse de l'entreprise"
    )

    logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL du logo de l'entreprise"
    )

    # ==========================================================
    # Contact
    # ==========================================================

    site_web: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Site web de l'entreprise"
    )

    telephone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Numéro de téléphone"
    )

    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Description de l'entreprise"
    )

    # ==========================================================
    # Statut
    # ==========================================================

    statut: Mapped[StatutEntreprise] = mapped_column(
        SAEnum(StatutEntreprise, name="statut_entreprise"),
        default=StatutEntreprise.active,
        server_default=StatutEntreprise.active.value,
        nullable=False,
        comment="Statut de l'entreprise (active, suspendue)"
    )

    motif_suspension: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Motif de la suspension (si applicable)"
    )

    # ==========================================================
    # Relations
    # ==========================================================

    utilisateurs: Mapped[list["Utilisateur"]] = relationship(
        back_populates="entreprise",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    campagnes: Mapped[list["Campagne"]] = relationship(
        back_populates="entreprise",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    abonnement: Mapped[Optional["Abonnement"]] = relationship(
        back_populates="entreprise",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # ==========================================================
    # Propriétés calculées
    # ==========================================================

    @property
    def est_active(self) -> bool:
        """Indique si l'entreprise est active."""
        return self.statut == StatutEntreprise.active

    @property
    def est_suspendue(self) -> bool:
        """Indique si l'entreprise est suspendue."""
        return self.statut == StatutEntreprise.suspendue

    @property
    def nombre_utilisateurs(self) -> int:
        """Nombre total d'utilisateurs de l'entreprise."""
        return len(self.utilisateurs)

    @property
    def nombre_utilisateurs_actifs(self) -> int:
        """Nombre d'utilisateurs actifs de l'entreprise."""
        return sum(1 for u in self.utilisateurs if u.actif)

    @property
    def nombre_campagnes(self) -> int:
        """Nombre total de campagnes de l'entreprise."""
        return len(self.campagnes)

    @property
    def nombre_campagnes_actives(self) -> int:
        """Nombre de campagnes actives de l'entreprise."""
        return sum(1 for c in self.campagnes if c.est_active)

    @property
    def a_abonnement_actif(self) -> bool:
        """Indique si l'entreprise a un abonnement actif."""
        return (
            self.abonnement is not None and
            self.abonnement.est_actif
        )

    @property
    def informations_contact(self) -> dict[str, str | None]:
        """Retourne les informations de contact de l'entreprise."""
        return {
            "nom": self.nom,
            "telephone": self.telephone,
            "site_web": self.site_web,
            "adresse": self.adresse,
        }

    # ==========================================================
    # Méthodes
    # ==========================================================

    def suspendre(self, motif: str) -> None:
        """Suspend l'entreprise avec un motif.
        
        Args:
            motif: Motif de la suspension
        """
        self.statut = StatutEntreprise.suspendue
        self.motif_suspension = motif

    def reactiver(self) -> None:
        """Réactive l'entreprise après une suspension."""
        self.statut = StatutEntreprise.active
        self.motif_suspension = None

    def mettre_a_jour_abonnement(self, abonnement: "Abonnement") -> None:
        """Met à jour l'abonnement de l'entreprise."""
        self.abonnement = abonnement

    def __repr__(self) -> str:
        """Représentation lisible de l'entreprise."""
        return (
            f"<Entreprise id={self.id} "
            f"nom={self.nom} "
            f"statut={self.statut.value} "
            f"utilisateurs={self.nombre_utilisateurs}>"
        )
