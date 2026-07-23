"""Modèle pour l'audit trail."""

import uuid
from typing import TYPE_CHECKING, Any, Optional

from fastapi import Request
from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.utilisateur import Utilisateur


class AuditLog(UUIDMixin, TimestampMixin, Base):
    """Journal d'audit pour tracer toutes les modifications.
    
    Enregistre toutes les actions CRUD effectuées sur les données
    sensibles de l'application avec les métadonnées associées.
    """
    
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_table_name", "table_name"),
        Index("ix_audit_logs_record_id", "record_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    # ==========================================================
    # Informations sur l'entité modifiée
    # ==========================================================
    
    table_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nom de la table modifiée"
    )
    
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="ID de l'enregistrement modifié"
    )

    # ==========================================================
    # Action réalisée
    # ==========================================================
    
    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Action réalisée (CREATE, UPDATE, DELETE, LOGIN, LOGOUT)"
    )

    # ==========================================================
    # Utilisateur
    # ==========================================================
    
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID de l'utilisateur ayant réalisé l'action"
    )
    
    user_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Email de l'utilisateur (redondant pour recherche)"
    )

    # ==========================================================
    # Modifications
    # ==========================================================
    
    changes: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Changements effectués (ancienne/valeur nouvelle)"
    )

    # ==========================================================
    # Métadonnées de la requête
    # ==========================================================
    
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="Adresse IP de l'utilisateur"
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="User-Agent du navigateur/client"
    )
    
    request_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        comment="ID unique de la requête (pour traçabilité)"
    )

    # ==========================================================
    # Date (héritée de TimestampMixin)
    # ==========================================================
    
    # created_at est hérité de TimestampMixin

    # ==========================================================
    # Méthodes de création
    # ==========================================================

    @classmethod
    def create_log(
        cls,
        table_name: str,
        record_id: uuid.UUID,
        action: str,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
        changes: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> "AuditLog":
        """
        Crée une nouvelle entrée de journal d'audit.

        Args:
            table_name: Nom de la table modifiée
            record_id: ID de l'enregistrement modifié
            action: Action réalisée (CREATE, UPDATE, DELETE, LOGIN, LOGOUT)
            user_id: ID de l'utilisateur
            user_email: Email de l'utilisateur
            changes: Changements effectués
            ip_address: Adresse IP de l'utilisateur
            user_agent: User-Agent du navigateur
            request_id: ID unique de la requête

        Returns:
            AuditLog: L'entrée de journal créée
        """
        return cls(
            table_name=table_name,
            record_id=record_id,
            action=action.upper(),
            user_id=user_id,
            user_email=user_email,
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

    @classmethod
    def log_create(
        cls,
        table_name: str,
        record_id: uuid.UUID,
        data: dict,
        **kwargs,
    ) -> "AuditLog":
        """Log une création."""
        return cls.create_log(
            table_name=table_name,
            record_id=record_id,
            action="CREATE",
            changes={"new": data},
            **kwargs,
        )

    @classmethod
    def log_update(
        cls,
        table_name: str,
        record_id: uuid.UUID,
        old_data: dict,
        new_data: dict,
        **kwargs,
    ) -> "AuditLog":
        """Log une mise à jour."""
        return cls.create_log(
            table_name=table_name,
            record_id=record_id,
            action="UPDATE",
            changes={"old": old_data, "new": new_data},
            **kwargs,
        )

    @classmethod
    def log_delete(
        cls,
        table_name: str,
        record_id: uuid.UUID,
        data: dict,
        **kwargs,
    ) -> "AuditLog":
        """Log une suppression."""
        return cls.create_log(
            table_name=table_name,
            record_id=record_id,
            action="DELETE",
            changes={"deleted": data},
            **kwargs,
        )

    @classmethod
    def log_login(
        cls,
        user_id: uuid.UUID,
        user_email: str,
        **kwargs,
    ) -> "AuditLog":
        """Log une connexion."""
        return cls.create_log(
            table_name="auth",
            record_id=user_id,
            action="LOGIN",
            user_id=user_id,
            user_email=user_email,
            changes={"event": "login"},
            **kwargs,
        )

    @classmethod
    def log_logout(
        cls,
        user_id: uuid.UUID,
        user_email: str,
        **kwargs,
    ) -> "AuditLog":
        """Log une déconnexion."""
        return cls.create_log(
            table_name="auth",
            record_id=user_id,
            action="LOGOUT",
            user_id=user_id,
            user_email=user_email,
            changes={"event": "logout"},
            **kwargs,
        )

    @classmethod
    def log_failed_login(
        cls,
        email: str,
        ip_address: str,
        **kwargs,
    ) -> "AuditLog":
        """Log une tentative de connexion échouée."""
        return cls.create_log(
            table_name="auth",
            record_id=uuid.uuid4(),
            action="FAILED_LOGIN",
            user_email=email,
            ip_address=ip_address,
            changes={"event": "failed_login", "email": email},
            **kwargs,
        )

    # ==========================================================
    # Méthodes utilitaires
    # ==========================================================

    def __repr__(self) -> str:
        """Représentation lisible de l'audit log."""
        return (
            f"<AuditLog id={self.id} "
            f"table={self.table_name} "
            f"record={self.record_id} "
            f"action={self.action} "
            f"user={self.user_email}>"
        )

    @property
    def is_create(self) -> bool:
        """Vérifie si l'action est une création."""
        return self.action == "CREATE"

    @property
    def is_update(self) -> bool:
        """Vérifie si l'action est une mise à jour."""
        return self.action == "UPDATE"

    @property
    def is_delete(self) -> bool:
        """Vérifie si l'action est une suppression."""
        return self.action == "DELETE"

    @property
    def is_login(self) -> bool:
        """Vérifie si l'action est une connexion."""
        return self.action in ("LOGIN", "LOGOUT", "FAILED_LOGIN")


# ==========================================================
# Fonction utilitaire pour le logging automatique
# ==========================================================

def log_action(
    db: Session,
    table_name: str,
    record_id: uuid.UUID,
    action: str,
    user: Optional["Utilisateur"] = None,
    changes: Optional[dict] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    """
    Fonction utilitaire pour logger une action avec les métadonnées de la requête.

    Args:
        db: Session SQLAlchemy
        table_name: Nom de la table modifiée
        record_id: ID de l'enregistrement
        action: Action réalisée
        user: Utilisateur connecté (optionnel)
        changes: Changements effectués
        request: Requête FastAPI (optionnel)

    Returns:
        AuditLog: L'entrée de journal créée
    """
    audit = AuditLog.create_log(
        table_name=table_name,
        record_id=record_id,
        action=action,
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        changes=changes,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        request_id=getattr(request.state, "request_id", None) if request else None,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit