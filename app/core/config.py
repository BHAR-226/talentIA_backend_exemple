"""Configuration applicative, chargée depuis l'environnement (fichier .env).

Un seul point de vérité pour tous les réglages (DB, sécurité, CORS). Voir
`.env.example` pour la liste des variables et leurs valeurs par défaut de dev.
"""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration de l'application."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ==========================================================
    # Application
    # ==========================================================
    
    app_name: str = "TalentIA API"
    environment: str = "development"
    debug: bool = True

    # ==========================================================
    # Base de données
    # ==========================================================
    
    database_url: str = "postgresql+psycopg://talentia:talentia@localhost:5432/talentia"

    # ==========================================================
    # Redis (pour cache et rate limiting)
    # ==========================================================
    
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False

    # ==========================================================
    # Sécurité / Auth (JWT transporté par un cookie httpOnly)
    # ==========================================================
    
    secret_key: str = "change-me-en-production"
    access_token_expire_minutes: int = 60
    auth_cookie_name: str = "talentia_session"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    # ==========================================================
    # CORS (origines autorisées du frontend)
    # ==========================================================
    
    cors_origins: str = "http://localhost:3000"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Retourne la liste des origines CORS autorisées."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ==========================================================
    # Frontend (sert à construire le lien de vérification d'email)
    # ==========================================================
    
    frontend_url: str = "http://localhost:3000"

    # ==========================================================
    # Vérification d'email
    # ==========================================================
    
    email_verification_expire_minutes: int = 20

    # ==========================================================
    # SMTP (envoi des emails de vérification)
    # ==========================================================
    
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@talentia.app"
    smtp_use_tls: bool = True

    @property
    def smtp_configured(self) -> bool:
        """Vérifie si le SMTP est configuré."""
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    # ==========================================================
    # Upload de CV
    # ==========================================================
    
    cv_upload_dir: str = "app/static/cv"
    cv_max_size_mb: int = 5
    cv_allowed_extensions: List[str] = [".pdf", ".doc", ".docx"]
    cv_allowed_mime_types: List[str] = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]

    @property
    def cv_max_size_bytes(self) -> int:
        """Taille maximale du CV en octets."""
        return self.cv_max_size_mb * 1024 * 1024

    # ==========================================================
    # Anti brute-force
    # ==========================================================
    
    login_max_tentatives: int = 5
    login_blocage_minutes: int = 15

    # ==========================================================
    # ClamAV (scan antivirus)
    # ==========================================================
    
    clamav_enabled: bool = False
    clamav_host: str = "localhost"
    clamav_port: int = 3310

    # ==========================================================
    # Export
    # ==========================================================
    
    export_max_rows: int = 10000

    # ==========================================================
    # Backup
    # ==========================================================
    
    backup_dir: str = "backups"
    backup_keep_count: int = 7
    backup_compression: bool = True

    # ==========================================================
    # Logging
    # ==========================================================
    
    log_level: str = "INFO"
    log_format: str = "json"  # "json" ou "text"

    # ==========================================================
    # Environnement
    # ==========================================================
    
    @property
    def is_production(self) -> bool:
        """Vérifie si l'environnement est la production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Vérifie si l'environnement est le développement."""
        return self.environment == "development"

    @property
    def is_testing(self) -> bool:
        """Vérifie si l'environnement est le testing."""
        return self.environment == "testing"


# Instance globale des settings
settings = Settings()


# ==========================================================
# Validation au démarrage
# ==========================================================

def validate_settings() -> None:
    """
    Valide les paramètres de configuration critiques.
    À appeler au démarrage de l'application.
    """
    import logging
    logger = logging.getLogger("talentia.config")
    
    # Vérifier la clé secrète en production
    if settings.is_production and settings.secret_key == "change-me-en-production":
        logger.warning(
            "⚠️ SECRET_KEY par défaut utilisée en production ! "
            "Veuillez définir une clé sécurisée dans l'environnement."
        )
    
    # Vérifier le cookie secure en production
    if settings.is_production and not settings.cookie_secure:
        logger.warning(
            "⚠️ COOKIE_SECURE=false en production ! "
            "Les cookies circuleront en clair hors HTTPS."
        )
    
    # Vérifier le SMTP en production
    if settings.is_production and not settings.smtp_configured:
        logger.warning(
            "⚠️ SMTP non configuré en production ! "
            "Les emails de vérification ne seront pas envoyés."
        )
    
    # Vérifier Redis si activé
    if settings.redis_enabled:
        try:
            import redis
            r = redis.Redis.from_url(settings.redis_url)
            r.ping()
            logger.info("✅ Redis connection successful")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            if settings.is_production:
                raise RuntimeError(f"Redis connection failed: {e}") from e