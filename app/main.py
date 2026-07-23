"""Point d'entrée de l'API TalentIA.

Assemble l'application : CORS (avec credentials pour le cookie de session),
handlers d'erreurs unifiés et routers.
"""

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

# Imports des routes
from app.api.routes import (
    abonnements,
    admin,
    auth,
    campagnes,
    candidats,
    candidatures,
    entreprises,
    health,
    offres,
    users,
)
from app.core.backup import scheduled_backup
from app.core.config import settings
from app.core.middleware import (
    CacheInvalidationMiddleware,
    ErrorHandlingMiddleware,
    MetricsMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.responses import (
    http_exception_handler,
    validation_exception_handler,
)

logger = logging.getLogger("talentia.main")

# Création de l'application FastAPI
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API TalentIA ATS — socle (Lot 0) + Tangara (utilisateurs, auth) + Offres & Campagnes + Candidatures.",
)

# ============================================================================
# MIDDLEWARE
# ============================================================================

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,  # indispensable pour le cookie httpOnly
    allow_methods=["*"],
    allow_headers=["*"],
)

# Métriques Prometheus
app.add_middleware(MetricsMiddleware)

# Cache invalidation
app.add_middleware(CacheInvalidationMiddleware)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# En-têtes de sécurité (nosniff, X-Frame-Options, CSP en prod...)
app.add_middleware(SecurityHeadersMiddleware)

# Compression gzip des réponses (implémentation standard Starlette,
# testée et gérant le streaming — plus sûre que la version maison)
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Capture des erreurs non gérées (doit être la couche la plus externe :
# le dernier middleware ajouté est le plus externe chez Starlette)
app.add_middleware(ErrorHandlingMiddleware)

# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# ============================================================================
# STATIC FILES (CV uploads)
# ============================================================================

Path(settings.cv_upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/static/cv", StaticFiles(directory=settings.cv_upload_dir), name="cv")

# ============================================================================
# ROUTES
# ============================================================================

# Routes de base
app.include_router(health.router)
app.include_router(auth.router)

# Routes Entreprises & Abonnements
app.include_router(entreprises.router)
app.include_router(abonnements.router)
app.include_router(admin.router)

# Routes Utilisateurs (Tangara)
app.include_router(users.router)

# Routes Candidats
app.include_router(candidats.router)

# Routes Campagnes & Offres (Yasmine)
app.include_router(campagnes.router)
app.include_router(offres.router)

# Routes Candidatures (Bambara)
app.include_router(candidatures.router)

# Routes Métriques & Export (optionnelles)
from app.core.metrics import router as metrics_router
app.include_router(metrics_router)

from app.core.export import router as export_router
app.include_router(export_router)

# ============================================================================
# STARTUP EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Tâches exécutées au démarrage de l'application."""
    
    # 1. Vérification de la configuration de sécurité
    _verifier_config_securite()
    
    # 2. Démarrer la tâche de sauvegarde automatique en production
    if settings.environment == "production":
        asyncio.create_task(scheduled_backup())
        logger.info("✅ Tâche de sauvegarde automatique démarrée")
    
    # 3. Vérifier Redis si activé
    if settings.redis_enabled:
        try:
            import redis
            r = redis.Redis.from_url(settings.redis_url)
            r.ping()
            logger.info("✅ Redis connection successful")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}")


def _verifier_config_securite() -> None:
    """Alerte au démarrage si la config de prod n'est pas sécurisée."""
    if settings.environment == "production":
        if not settings.cookie_secure:
            logger.warning(
                "⚠️ COOKIE_SECURE=false en production : le cookie de session "
                "circulera en clair hors HTTPS. À corriger."
            )
        if settings.secret_key == "change-me-en-production":
            logger.warning(
                "⚠️ SECRET_KEY par défaut utilisée en production : à changer immédiatement."
            )


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "success": True,
        "message": f"{settings.app_name} — documentation sur /docs",
        "environment": settings.environment
    }