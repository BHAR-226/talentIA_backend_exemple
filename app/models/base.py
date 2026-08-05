"""Mixins communs aux modèles : identifiant UUID, horodatages, soft delete et verrouillage optimiste."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDMixin:
    """Mixin ajoutant un identifiant UUID comme clé primaire."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Identifiant unique de l'enregistrement"
    )


class TimestampMixin:
    """Mixin ajoutant les horodatages de création et de mise à jour."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Date et heure de création"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Date et heure de dernière modification"
    )


class SoftDeleteMixin:
    """Mixin permettant la suppression logique (soft delete) des enregistrements.

    Les enregistrements supprimés logiquement ne sont pas physiquement retirés
    de la base de données, mais marqués comme supprimés. Cela permet de :
    - Conserver l'historique des données
    - Restaurer des enregistrements supprimés
    - Maintenir l'intégrité référentielle
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date et heure de la suppression logique"
    )

    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID de l'utilisateur qui a effectué la suppression"
    )

    @property
    def is_deleted(self) -> bool:
        """Indique si l'enregistrement est supprimé logiquement."""
        return self.deleted_at is not None

    @property
    def is_active(self) -> bool:
        """Indique si l'enregistrement est actif (non supprimé)."""
        return not self.is_deleted

    def soft_delete(self, user_id: uuid.UUID | None = None) -> None:
        """Marque l'enregistrement comme supprimé logiquement.

        Args:
            user_id: ID de l'utilisateur effectuant la suppression (optionnel)
        """
        self.deleted_at = datetime.now(UTC)
        if user_id:
            self.deleted_by = user_id

    def restore(self) -> None:
        """Restaure un enregistrement supprimé logiquement."""
        self.deleted_at = None
        self.deleted_by = None


class OptimisticLockMixin:
    """Mixin ajoutant un verrouillage optimiste pour éviter les mises à jour concurrentes.

    Le champ `version` est incrémenté à chaque mise à jour. Si deux utilisateurs
    tentent de modifier le même enregistrement, le second verra une erreur de
    conflit (version mismatch).
    """

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Version de l'enregistrement (verrouillage optimiste)"
    )

    def increment_version(self) -> None:
        """Incrémente la version de l'enregistrement."""
        self.version += 1

    def check_version(self, expected_version: int) -> bool:
        """Vérifie si la version correspond à celle attendue.

        Args:
            expected_version: Version attendue

        Returns:
            True si les versions correspondent, False sinon
        """
        return self.version == expected_version
