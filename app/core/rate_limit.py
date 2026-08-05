"""Anti brute-force avec support Redis optionnel."""

import logging
import time
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger("talentia.rate_limit")

# Tentative d'import Redis
try:
    import redis
    _redis_available = True
except ImportError:
    _redis_available = False


# ==========================================================
# Configuration
# ==========================================================

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BLOCK_MINUTES = 15
DEFAULT_PREFIX = "rate_limit"


# ==========================================================
# Structures de données
# ==========================================================

@dataclass
class _Compteur:
    """Compteur de tentatives en mémoire."""
    tentatives: int = 0
    bloque_jusqu_a: float = 0.0

    @property
    def est_bloque(self) -> bool:
        """Vérifie si le compteur est bloqué."""
        return time.monotonic() < self.bloque_jusqu_a

    @property
    def secondes_restantes(self) -> float:
        """Retourne les secondes restantes avant déblocage."""
        if not self.est_bloque:
            return 0.0
        return self.bloque_jusqu_a - time.monotonic()


_compteurs: dict[str, _Compteur] = {}
_redis_client = None

# Initialisation Redis
if _redis_available and settings.redis_enabled:
    try:
        _redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        _redis_client.ping()
        logger.info("✅ Redis rate limiting enabled")
    except Exception as e:
        logger.warning(f"⚠️ Redis unavailable, using in-memory rate limiting: {e}")
        _redis_client = None


# ==========================================================
# Fonctions utilitaires
# ==========================================================

def _cle(email: str) -> str:
    """Normalise une clé email."""
    return email.strip().lower()


def _get_redis_keys(key: str) -> tuple[str, str]:
    """Retourne les clés Redis pour un email."""
    prefix = DEFAULT_PREFIX
    return (
        f"{prefix}:attempts:{key}",
        f"{prefix}:block:{key}",
    )


# ==========================================================
# Fonctions principales
# ==========================================================

def verifier_non_bloque(email: str) -> float | None:
    """Vérifie si un email est bloqué.

    Args:
        email: Email à vérifier

    Returns:
        Optional[float]: Secondes restantes si bloqué, None sinon
    """
    key = _cle(email)

    # Utiliser Redis si disponible
    if _redis_client:
        try:
            _, block_key = _get_redis_keys(key)
            remaining = _redis_client.ttl(block_key)
            if remaining > 0:
                return float(remaining)
            return None
        except Exception as e:
            logger.error(f"Redis rate limit check error: {e}")
            # Fallback to in-memory

    # In-memory fallback
    compteur = _compteurs.get(key)
    if compteur is None:
        return None

    if not compteur.est_bloque:
        return None

    return compteur.secondes_restantes


def enregistrer_echec(email: str) -> int:
    """Enregistre une tentative de connexion échouée.

    Args:
        email: Email concerné

    Returns:
        int: Nombre de tentatives après incrémentation
    """
    key = _cle(email)
    max_attempts = settings.login_max_tentatives or DEFAULT_MAX_ATTEMPTS
    block_minutes = settings.login_blocage_minutes or DEFAULT_BLOCK_MINUTES

    # Utiliser Redis si disponible
    if _redis_client:
        try:
            attempts_key, block_key = _get_redis_keys(key)

            # Incrémenter les tentatives
            attempts = _redis_client.incr(attempts_key)
            _redis_client.expire(attempts_key, block_minutes * 60)

            # Vérifier si le seuil est atteint
            if attempts >= max_attempts:
                _redis_client.setex(block_key, block_minutes * 60, "blocked")
                logger.warning(f"🚫 Rate limit exceeded for {email}")

            return attempts

        except Exception as e:
            logger.error(f"Redis rate limit increment error: {e}")
            # Fallback to in-memory

    # In-memory fallback
    compteur = _compteurs.setdefault(key, _Compteur())
    compteur.tentatives += 1

    if compteur.tentatives >= max_attempts:
        compteur.bloque_jusqu_a = time.monotonic() + block_minutes * 60
        logger.warning(f"🚫 Rate limit exceeded (in-memory) for {email}")

    return compteur.tentatives


def reinitialiser(email: str) -> None:
    """Réinitialise le compteur de tentatives après une connexion réussie."""
    key = _cle(email)

    # Utiliser Redis si disponible
    if _redis_client:
        try:
            attempts_key, block_key = _get_redis_keys(key)
            _redis_client.delete(attempts_key)
            _redis_client.delete(block_key)
            logger.debug(f"🔄 Rate limit reset for {email}")
            return
        except Exception as e:
            logger.error(f"Redis rate limit reset error: {e}")

    # In-memory fallback
    _compteurs.pop(key, None)
    logger.debug(f"🔄 Rate limit reset (in-memory) for {email}")


def get_attempts(email: str) -> int:
    """Récupère le nombre de tentatives pour un email.

    Args:
        email: Email concerné

    Returns:
        int: Nombre de tentatives
    """
    key = _cle(email)

    if _redis_client:
        try:
            attempts_key, _ = _get_redis_keys(key)
            attempts = _redis_client.get(attempts_key)
            return int(attempts) if attempts else 0
        except Exception as e:
            logger.error(f"Redis rate limit get attempts error: {e}")

    compteur = _compteurs.get(key)
    return compteur.tentatives if compteur else 0


def is_blocked(email: str) -> bool:
    """Vérifie si un email est bloqué.

    Args:
        email: Email concerné

    Returns:
        bool: True si bloqué
    """
    remaining = verifier_non_bloque(email)
    return remaining is not None and remaining > 0


def get_block_duration(email: str) -> int:
    """Récupère la durée de blocage restante en secondes.

    Args:
        email: Email concerné

    Returns:
        int: Secondes restantes (0 si non bloqué)
    """
    remaining = verifier_non_bloque(email)
    return int(remaining) if remaining else 0


def get_status(email: str) -> dict:
    """Retourne le statut complet du rate limiting pour un email.

    Args:
        email: Email concerné

    Returns:
        dict: Statut complet
    """
    attempts = get_attempts(email)
    blocked = is_blocked(email)
    remaining = get_block_duration(email)

    return {
        "email": email,
        "attempts": attempts,
        "is_blocked": blocked,
        "block_remaining_seconds": remaining,
        "block_remaining_minutes": round(remaining / 60, 1) if remaining else 0,
        "max_attempts": settings.login_max_tentatives or DEFAULT_MAX_ATTEMPTS,
        "block_duration_minutes": settings.login_blocage_minutes or DEFAULT_BLOCK_MINUTES,
    }


# ==========================================================
# Middleware pour le rate limiting
# ==========================================================

class RateLimitMiddleware:
    """Middleware pour appliquer le rate limiting sur toutes les routes."""

    def __init__(self, path_prefix: str = "/api", max_attempts: int = 100, block_minutes: int = 5):
        self.path_prefix = path_prefix
        self.max_attempts = max_attempts
        self.block_minutes = block_minutes

    async def __call__(self, request, call_next):
        # Récupérer l'IP du client
        client_ip = request.client.host if request.client else "unknown"

        # Vérifier le rate limiting
        if request.url.path.startswith(self.path_prefix) and is_blocked(client_ip):
            remaining = get_block_duration(client_ip)
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Trop de requêtes. Réessayez dans {int(remaining // 60) + 1} minutes."
            )

        response = await call_next(request)

        # Ajouter les headers de rate limiting
        if request.url.path.startswith(self.path_prefix):
            attempts = get_attempts(client_ip)
            max_attempts = self.max_attempts
            remaining = max(0, max_attempts - attempts)

            response.headers["X-RateLimit-Limit"] = str(max_attempts)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + self.block_minutes * 60)

        return response


# ==========================================================
# Décorateur pour le rate limiting
# ==========================================================

def rate_limit(max_attempts: int = 5, block_minutes: int = 15):
    """Décorateur pour appliquer le rate limiting sur une route spécifique.

    Usage:
        @router.post("/login")
        @rate_limit(max_attempts=3, block_minutes=10)
        def login(...):
            ...
    """
    def decorator(func):
        from functools import wraps

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Récupérer l'email ou l'IP du client
            # À adapter selon la route
            identifier = kwargs.get("email") or kwargs.get("identifier") or "unknown"

            if is_blocked(identifier):
                from fastapi import HTTPException, status
                remaining = get_block_duration(identifier)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Trop de tentatives. Réessayez dans {int(remaining // 60) + 1} minutes."
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator
