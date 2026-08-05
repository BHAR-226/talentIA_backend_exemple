"""Middleware personnalisés pour l'application."""

import logging
import time
import uuid
from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.cache import cache
from app.core.config import settings

logger = logging.getLogger("talentia.middleware")


# ==========================================================
# Middleware de logging des requêtes
# ==========================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware pour logger les requêtes et mesurer les performances."""

    # Routes à exclure du logging (pour réduire le bruit)
    EXCLUDED_PATHS = {
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    # Routes avec logging minimal
    MINIMAL_PATHS = {
        "/health",
        "/metrics",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Vérifier si la route est exclue
        path = request.url.path
        if path in self.EXCLUDED_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.perf_counter()

        # Log entrée (sauf pour les routes minimales)
        if path not in self.MINIMAL_PATHS:
            logger.info(
                f"➡️ Request started: {request.method} {path}",
                extra={
                    'request_id': request_id,
                    'method': request.method,
                    'path': path,
                    'client_ip': request.client.host if request.client else None,
                    'user_agent': request.headers.get('user-agent'),
                    'referer': request.headers.get('referer'),
                }
            )

        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(
                f"❌ Request failed: {str(e)}",
                extra={
                    'request_id': request_id,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
            raise

        duration = time.perf_counter() - start_time
        duration_ms = duration * 1000

        # Log sortie (sauf pour les routes minimales)
        if path not in self.MINIMAL_PATHS:
            logger.info(
                f"⬅️ Request completed: {response.status_code} - {duration_ms:.2f}ms",
                extra={
                    'request_id': request_id,
                    'status_code': response.status_code,
                    'duration_ms': duration_ms,
                }
            )

        # Alerte pour les requêtes lentes
        if duration > 1.0:
            logger.warning(
                f"🐢 Slow request: {request.method} {path} took {duration:.2f}s",
                extra={
                    'request_id': request_id,
                    'method': request.method,
                    'path': path,
                    'duration': duration,
                    'status_code': response.status_code,
                }
            )

        # Ajouter les headers de traçabilité
        response.headers['X-Request-ID'] = request_id
        response.headers['X-Response-Time'] = f"{duration_ms:.2f}ms"

        return response


# ==========================================================
# Middleware d'invalidation du cache
# ==========================================================

class CacheInvalidationMiddleware(BaseHTTPMiddleware):
    """Middleware pour invalider le cache après les modifications."""

    # Mapping des routes vers les patterns d'invalidation
    INVALIDATION_MAP = {
        "users": "user:*",
        "offres": "offre:*",
        "campagnes": "campagne:*",
        "candidatures": "candidature:*",
        "entreprises": "entreprise:*",
        "admin": "admin_stats:*",
        "abonnements": "abonnement:*",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Exécuter la requête
        response = await call_next(request)

        # Invalider le cache si méthode modificative
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            await self._invalidate_cache(request)

        return response

    async def _invalidate_cache(self, request: Request) -> None:
        """Invalide le cache en fonction de la route."""
        path_parts = request.url.path.split('/')
        if len(path_parts) > 1:
            resource = path_parts[1]  # users, offres, etc.

            # Utiliser le mapping si disponible
            pattern = self.INVALIDATION_MAP.get(resource, f"*{resource}*")

            # Invalider le cache
            deleted = await cache.invalidate_pattern(pattern)
            if deleted > 0:
                logger.debug(f"🗑️ Invalidated {deleted} cache keys for pattern: {pattern}")


# ==========================================================
# Middleware de sécurité
# ==========================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware pour ajouter des en-têtes de sécurité."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Ajouter les en-têtes de sécurité
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # CSP en production
        if settings.is_production:
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )

        return response


# ==========================================================
# Middleware de gestion des erreurs
# ==========================================================

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware pour capturer et logger les erreurs non gérées."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except Exception as e:
            # Log l'erreur avec le contexte
            logger.error(
                f"❌ Unhandled error: {str(e)}",
                extra={
                    'path': request.url.path,
                    'method': request.method,
                    'error_type': type(e).__name__,
                    'error': str(e),
                },
                exc_info=True
            )
            raise


# ==========================================================
# Middleware de métriques (version améliorée)
# ==========================================================

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware pour collecter des métriques Prometheus."""

    # Routes à exclure
    EXCLUDED_PATHS = {
        "/metrics",
        "/health",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Exclure certaines routes
        if path in self.EXCLUDED_PATHS:
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        # Log des métriques en production
        if settings.is_production:
            logger.debug(
                f"📊 METRIC: {request.method} {path} {response.status_code} {duration:.3f}s"
            )

        return response


# ==========================================================
# Middleware de compression (optionnel)
# ==========================================================

class CompressionMiddleware(BaseHTTPMiddleware):
    """Middleware pour compresser les réponses (gzip).

    NOTE: pour un usage en production, préférer `starlette.middleware.gzip.
    GZipMiddleware` (déjà testé, gère le streaming). Cette version est
    conservée pour compatibilité mais compresse réellement le corps (le
    code précédent posait le header `content-encoding: gzip` SANS
    compresser les octets, ce qui aurait cassé tout client essayant de
    décompresser la réponse).
    """

    MIN_SIZE = 1024  # Taille minimum pour compresser (1KB)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Vérifier si la réponse peut être compressée
        if (
            response.status_code < 400 and
            response.headers.get('content-type', '').startswith('application/json') and
            len(response.body) > self.MIN_SIZE and
            'gzip' in request.headers.get('accept-encoding', '')
        ):
            import gzip as gzip_module

            compressed_body = gzip_module.compress(response.body)
            response.headers['content-encoding'] = 'gzip'
            response.headers['content-length'] = str(len(compressed_body))
            response.headers.setdefault('vary', 'Accept-Encoding')
            return Response(
                content=compressed_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response


# ==========================================================
# Fonction pour ajouter tous les middlewares
# ==========================================================

def setup_middlewares(app) -> None:
    """Configure tous les middlewares pour l'application.

    Args:
        app: Instance FastAPI
    """
    # Ordre d'exécution (du plus externe au plus interne)
    # 1. Compression
    # 2. Sécurité
    # 3. Métriques
    # 4. Logging
    # 5. Cache invalidation
    # 6. Erreurs

    # D'abord les middlewares qui s'exécutent en premier (externe)
    app.add_middleware(CompressionMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CacheInvalidationMiddleware)
    # En dernier, le middleware d'erreurs (interne)
    app.add_middleware(ErrorHandlingMiddleware)
