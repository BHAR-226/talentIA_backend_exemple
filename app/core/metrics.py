"""Métriques Prometheus pour le monitoring."""

import re
import time
from collections.abc import Callable

from fastapi import APIRouter
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

# ==========================================================
# Définition des métriques
# ==========================================================

# Compteur de requêtes HTTP
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# Durée des requêtes HTTP
REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Utilisateurs actifs
ACTIVE_USERS = Gauge(
    'active_users_total',
    'Number of active users',
    ['type']  # 'candidat' or 'utilisateur'
)

# Requêtes en cours
REQUESTS_IN_PROGRESS = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests currently in progress'
)

# Erreurs par type
ERRORS_BY_TYPE = Counter(
    'http_errors_total',
    'HTTP errors by type',
    ['type', 'status']
)

# Temps de réponse par percentile
RESPONSE_TIME_PERCENTILES = Histogram(
    'http_response_time_percentiles',
    'HTTP response time percentiles',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]
)

# Statistiques de la base de données
DB_CONNECTION_POOL = Gauge(
    'db_connection_pool',
    'Database connection pool status',
    ['state']  # 'used', 'available', 'total'
)

# Métriques de cache
CACHE_HITS = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_type']
)

CACHE_MISSES = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_type']
)


# ==========================================================
# Middleware
# ==========================================================

class MetricsMiddleware:
    """Middleware pour collecter automatiquement les métriques HTTP."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next: Callable):
        # Incrémenter les requêtes en cours
        REQUESTS_IN_PROGRESS.inc()

        start = time.time()

        try:
            response = await call_next(request)
        except Exception as e:
            # Compter les erreurs
            error_type = type(e).__name__
            ERRORS_BY_TYPE.labels(
                type=error_type,
                status='500'
            ).inc()
            raise

        duration = time.time() - start

        # Normaliser le path pour éviter la cardinalité infinie
        path = _normalize_path(request.url.path)

        # Enregistrer les métriques
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=path,
            status=response.status_code
        ).inc()

        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=path
        ).observe(duration)

        RESPONSE_TIME_PERCENTILES.labels(
            method=request.method,
            endpoint=path
        ).observe(duration)

        # Compter les erreurs 4xx et 5xx
        if response.status_code >= 400:
            ERRORS_BY_TYPE.labels(
                type='http_error',
                status=response.status_code
            ).inc()

        # Décrémenter les requêtes en cours
        REQUESTS_IN_PROGRESS.dec()

        return response


# ==========================================================
# Utilitaires
# ==========================================================

def _normalize_path(path: str) -> str:
    """Normalise un chemin pour réduire la cardinalité."""
    # UUID
    path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
    # IDs numériques
    path = re.sub(r'/\d+', '/{id}', path)
    # Emails dans les URLs
    path = re.sub(r'/[\w\.-]+@[\w\.-]+\.\w+', '/{email}', path)
    return path


# ==========================================================
# Routeur FastAPI
# ==========================================================

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def metrics():
    """Endpoint Prometheus pour récupérer les métriques.
    
    **Usage:** Configurer Prometheus pour scraper cet endpoint.
    """
    return Response(generate_latest(), media_type="text/plain")


# ==========================================================
# Fonctions de mise à jour des métriques
# ==========================================================

def update_active_users_metrics(db: Session) -> None:
    """Met à jour la métrique des utilisateurs actifs."""
    from app.models.candidat import Candidat
    from app.models.utilisateur import Utilisateur

    # Compter les candidats actifs
    candidats_actifs = db.query(Candidat).filter(
        Candidat.email_verifie == True,
        Candidat.deleted_at.is_(None)
    ).count()

    # Compter les utilisateurs internes actifs
    utilisateurs_actifs = db.query(Utilisateur).filter(
        Utilisateur.actif == True,
        Utilisateur.email_verifie == True,
        Utilisateur.deleted_at.is_(None)
    ).count()

    # Mettre à jour les gauges
    ACTIVE_USERS.labels(type='candidat').set(candidats_actifs)
    ACTIVE_USERS.labels(type='utilisateur').set(utilisateurs_actifs)


def update_db_pool_metrics(engine) -> None:
    """Met à jour les métriques du pool de connexions."""
    pool = engine.pool
    DB_CONNECTION_POOL.labels(state='used').set(pool.checkedin())
    DB_CONNECTION_POOL.labels(state='available').set(pool.checkedout())
    DB_CONNECTION_POOL.labels(state='total').set(pool.size())


# ==========================================================
# Fonction pour les métriques de cache
# ==========================================================

def record_cache_metric(hit: bool, cache_type: str = "default") -> None:
    """Enregistre une métrique de cache.
    
    Args:
        hit: True si le cache a été touché, False sinon
        cache_type: Type de cache (default, user, stats, etc.)
    """
    if hit:
        CACHE_HITS.labels(cache_type=cache_type).inc()
    else:
        CACHE_MISSES.labels(cache_type=cache_type).inc()


# ==========================================================
# Décorateur pour les métriques de performance
# ==========================================================

def track_performance(name: str):
    """Décorateur pour suivre les performances d'une fonction.
    
    Usage:
        @track_performance("user_service")
        def get_user(id):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start
                # Enregistrer la métrique
                REQUEST_DURATION.labels(
                    method='function',
                    endpoint=name
                ).observe(duration)
                return result
            except Exception as e:
                ERRORS_BY_TYPE.labels(
                    type=type(e).__name__,
                    status='500'
                ).inc()
                raise
        return wrapper
    return decorator


# ==========================================================
# Initialisation des métriques
# ==========================================================

def init_metrics() -> None:
    """Initialise les métriques avec des valeurs par défaut."""
    # Initialiser les compteurs à 0
    REQUEST_COUNT.labels(method='GET', endpoint='/', status=200).inc(0)

    # Initialiser les gauges
    ACTIVE_USERS.labels(type='candidat').set(0)
    ACTIVE_USERS.labels(type='utilisateur').set(0)
    REQUESTS_IN_PROGRESS.set(0)


# ==========================================================
# Endpoint de diagnostic
# ==========================================================

@router.get("/metrics/diagnostic")
def metrics_diagnostic():
    """Endpoint de diagnostic pour vérifier l'état des métriques."""
    return {
        "status": "ok",
        "metrics_count": len([name for name in globals() if isinstance(globals()[name], (Counter, Histogram, Gauge))]),
        "registered_metrics": [
            name for name in globals()
            if isinstance(globals()[name], (Counter, Histogram, Gauge))
        ]
    }
