"""Utilisateur interne d'une entreprise (recruteur / admin RH / admin
plateforme / évaluateur technique). Le candidat est une entité distincte.
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import RoleUtilisateur
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.entreprise import Entreprise


class Utilisateur(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Modèle représentant un utilisateur interne d'une entreprise.

    Un utilisateur peut avoir différents rôles (recruteur, admin RH,
    évaluateur technique, admin plateforme) et est toujours rattaché
    à une entreprise.
    """

    __tablename__ = "utilisateurs"
    __table_args__ = (
        Index("ix_utilisateurs_entreprise_actif", "entreprise_id", "actif"),
        Index("ix_utilisateurs_entreprise_role", "entreprise_id", "role"),
        Index("ix_utilisateurs_email_verifie", "email", "email_verifie"),
        # Pas d'Index("ix_utilisateurs_email", "email") ici : `unique=True,
        # index=True` sur la colonne `email` ci-dessous crée déjà un index
        # unique nommé "ix_utilisateurs_email". En redéclarer un second avec
        # le même nom (mais non-unique) créait un conflit de nommage — les
        # deux se disputaient le même nom dans les migrations Alembic, ce qui
        # aurait fait échouer `CREATE INDEX` (nom déjà pris) au déploiement,
        # et rendait incertain si l'email était réellement unique en base.
    )

    # ==========================================================
    # Relations
    # ==========================================================

    entreprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entreprises.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID de l'entreprise de rattachement"
    )

    # ==========================================================
    # Informations personnelles
    # ==========================================================

    nom: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Nom complet de l'utilisateur"
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Adresse email (unique)"
    )

    mot_de_passe_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hash du mot de passe"
    )

    telephone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Numéro de téléphone"
    )

    fonction: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Fonction ou poste occupé"
    )

    # ==========================================================
    # Rôle et statut
    # ==========================================================

    role: Mapped[RoleUtilisateur] = mapped_column(
        SAEnum(RoleUtilisateur, name="role_utilisateur"),
        nullable=False,
        comment="Rôle de l'utilisateur"
    )

    actif: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Indique si le compte est actif"
    )

    email_verifie: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        comment="Indique si l'email a été vérifié"
    )

    # ==========================================================
    # Session
    # ==========================================================

    derniere_connexion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date et heure de la dernière connexion"
    )

    # ==========================================================
    # Relations
    # ==========================================================

    entreprise: Mapped["Entreprise"] = relationship(
        back_populates="utilisateurs",
        lazy="selectin"
    )

    # ==========================================================
    # Propriétés calculées
    # ==========================================================

    @property
    def est_admin_rh(self) -> bool:
        """Indique si l'utilisateur est admin RH."""
        return self.role == RoleUtilisateur.admin_rh

    @property
    def est_recruteur(self) -> bool:
        """Indique si l'utilisateur est recruteur."""
        return self.role == RoleUtilisateur.recruteur

    @property
    def est_admin_plateforme(self) -> bool:
        """Indique si l'utilisateur est admin plateforme."""
        return self.role == RoleUtilisateur.admin_plateforme

    @property
    def est_evaluateur_technique(self) -> bool:
        """Indique si l'utilisateur est évaluateur technique."""
        return self.role == RoleUtilisateur.evaluateur_technique

    @property
    def est_actif(self) -> bool:
        """Indique si le compte est actif et non supprimé."""
        return self.actif and not self.is_deleted

    @property
    def est_verifie(self) -> bool:
        """Indique si l'email est vérifié."""
        return self.email_verifie

    @property
    def peut_gerer_equipe(self) -> bool:
        """Indique si l'utilisateur peut gérer l'équipe (admin RH)."""
        return self.est_admin_rh or self.est_admin_plateforme

    @property
    def peut_creer_offres(self) -> bool:
        """Indique si l'utilisateur peut créer des offres."""
        return self.role in (
            RoleUtilisateur.recruteur,
            RoleUtilisateur.admin_rh,
            RoleUtilisateur.admin_plateforme
        )

    @property
    def peut_evaluer_candidats(self) -> bool:
        """Indique si l'utilisateur peut évaluer des candidats."""
        return self.role in (
            RoleUtilisateur.evaluateur_technique,
            RoleUtilisateur.recruteur,
            RoleUtilisateur.admin_rh,
            RoleUtilisateur.admin_plateforme
        )

    @property
    def est_super_admin(self) -> bool:
        """Indique si l'utilisateur est super admin (admin plateforme)."""
        return self.est_admin_plateforme

    @property
    def est_connecte(self) -> bool:
        """Indique si l'utilisateur s'est déjà connecté."""
        return self.derniere_connexion is not None

    # ==========================================================
    # Méthodes
    # ==========================================================

    def update_last_login(self) -> None:
        """Met à jour la date de dernière connexion."""
        self.derniere_connexion = datetime.now(UTC)

    def verifier_email(self) -> None:
        """Marque l'email comme vérifié."""
        self.email_verifie = True

    def desactiver(self) -> None:
        """Désactive le compte de l'utilisateur."""
        self.actif = False

    def activer(self) -> None:
        """Active le compte de l'utilisateur."""
        self.actif = True

    def promouvoir_admin_rh(self) -> None:
        """Promeut l'utilisateur au rôle admin RH."""
        self.role = RoleUtilisateur.admin_rh

    def promouvoir_recruteur(self) -> None:
        """Promeut l'utilisateur au rôle recruteur."""
        self.role = RoleUtilisateur.recruteur

    def promouvoir_evaluateur_technique(self) -> None:
        """Promeut l'utilisateur au rôle évaluateur technique."""
        self.role = RoleUtilisateur.evaluateur_technique

    def est_superieur_a(self, autre: "Utilisateur") -> bool:
        """Vérifie si l'utilisateur a un rôle supérieur à un autre.

        Args:
            autre: Autre utilisateur à comparer

        Returns:
            True si l'utilisateur a un rôle supérieur ou égal
        """
        hierarchy = {
            RoleUtilisateur.admin_plateforme: 4,
            RoleUtilisateur.admin_rh: 3,
            RoleUtilisateur.recruteur: 2,
            RoleUtilisateur.evaluateur_technique: 1,
        }
        return hierarchy.get(self.role, 0) >= hierarchy.get(autre.role, 0)

    def __repr__(self) -> str:
        """Représentation lisible de l'utilisateur."""
        return (
            f"<Utilisateur id={self.id} "
            f"nom={self.nom} "
            f"email={self.email} "
            f"role={self.role.value} "
            f"actif={self.actif}>"
        )
