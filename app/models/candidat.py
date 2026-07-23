"""Candidat — indépendant de toute entreprise (peut postuler partout). 
Le parsing du CV et l'enrichissement IA seront ajoutés au Lot 5.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.candidature import Candidature


class Candidat(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Modèle représentant un candidat indépendant de toute entreprise.
    
    Un candidat peut postuler à plusieurs offres et n'est pas lié à une
    entreprise spécifique. Il peut avoir un compte (avec mot de passe) ou
    être créé de manière anonyme lors d'une candidature.
    """
    
    __tablename__ = "candidats"
    __table_args__ = (
        # Pas d'Index("ix_candidats_email", "email") ici : `unique=True,
        # index=True` sur la colonne `email` crée déjà un index unique nommé
        # "ix_candidats_email" — en redéclarer un second non-unique avec le
        # même nom entrait en collision (même bug que sur `Utilisateur`).
        Index("ix_candidats_email_verifie", "email", "email_verifie"),
        Index("ix_candidats_nom", "nom"),
    )

    # ==========================================================
    # Informations personnelles
    # ==========================================================
    
    nom: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Nom complet du candidat"
    )
    
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Adresse email (unique)"
    )
    
    # Nullable : un candidat peut exister sans compte (créé lors d'une candidature
    # sans inscription) ; renseigné à l'inscription pour permettre la connexion.
    mot_de_passe_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Hash du mot de passe (null si pas de compte)"
    )
    
    telephone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Numéro de téléphone"
    )
    
    # ==========================================================
    # Profil professionnel
    # ==========================================================
    
    titre_principal: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Titre ou poste actuel"
    )
    
    annees_experience: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Nombre d'années d'expérience"
    )
    
    localisation: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Localisation géographique"
    )
    
    # ==========================================================
    # CV et vérification
    # ==========================================================
    
    cv_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL du CV uploadé"
    )
    
    email_verifie: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        comment="Indique si l'email a été vérifié"
    )
    
    # ==========================================================
    # Réseaux et portfolio
    # ==========================================================
    
    linkedin_url: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="URL du profil LinkedIn"
    )
    
    portfolio_url: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="URL du portfolio"
    )
    
    # ==========================================================
    # Disponibilité
    # ==========================================================
    
    disponibilite: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Disponibilité (immediate, 1 mois, etc.)"
    )
    
    preavis: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Durée du préavis en jours"
    )
    
    pret_a_relocaliser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Prêt à se relocaliser"
    )
    
    permis_conduire: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Possède un permis de conduire"
    )

    # ==========================================================
    # Relations
    # ==========================================================
    
    candidatures: Mapped[list["Candidature"]] = relationship(
        back_populates="candidat",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Candidature.created_at.desc()"
    )
    
    # ==========================================================
    # Propriétés calculées
    # ==========================================================
    
    @property
    def nombre_candidatures(self) -> int:
        """Nombre total de candidatures soumises."""
        return len(self.candidatures)
    
    @property
    def a_upload_cv(self) -> bool:
        """Indique si le candidat a uploadé un CV."""
        return self.cv_url is not None
    
    @property
    def est_connecte(self) -> bool:
        """Indique si le candidat a un compte (mot de passe hash)."""
        return self.mot_de_passe_hash is not None
    
    @property
    def est_verifie(self) -> bool:
        """Indique si le candidat a vérifié son email."""
        return self.email_verifie
    
    @property
    def disponibilite_texte(self) -> str:
        """Retourne la disponibilité en texte lisible."""
        if self.disponibilite:
            return self.disponibilite
        if self.preavis:
            return f"{self.preavis} jours de préavis"
        return "Non spécifiée"
    
    # ==========================================================
    # Méthodes
    # ==========================================================
    
    def verifier_email(self) -> None:
        """Marque l'email comme vérifié."""
        self.email_verifie = True
    
    def upload_cv(self, url: str) -> None:
        """Met à jour l'URL du CV.
        
        Args:
            url: Nouvelle URL du CV
        """
        self.cv_url = url
    
    def supprimer_cv(self) -> None:
        """Supprime le CV du candidat."""
        self.cv_url = None
    
    def __repr__(self) -> str:
        """Représentation lisible du candidat."""
        return (
            f"<Candidat id={self.id} "
            f"nom={self.nom} "
            f"email={self.email} "
            f"candidatures={self.nombre_candidatures}>"
        )