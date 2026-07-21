"""Configuration applicative, chargée depuis l'environnement (fichier .env).

Un seul point de vérité pour tous les réglages (DB, sécurité, CORS). Voir
`.env.example` pour la liste des variables et leurs valeurs par défaut de dev.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    app_name: str = "TalentIA API"
    environment: str = "development"
    debug: bool = True

    # Base de données
    database_url: str = "postgresql+psycopg://talentia:talentia@localhost:5432/talentia"

    # Sécurité / Auth (JWT transporté par un cookie httpOnly)
    secret_key: str = "change-me-en-production"
    access_token_expire_minutes: int = 60
    auth_cookie_name: str = "talentia_session"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    # CORS (origines autorisées du frontend), séparées par des virgules
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
