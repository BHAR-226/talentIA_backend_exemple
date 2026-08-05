"""Système de cache avec Redis."""

import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger("talentia.cache")

try:
    import redis.asyncio as redis
except ImportError:
    redis = None
    logger.warning("⚠️ redis package not installed. Cache will be disabled.")


class AsyncCache:
    """Cache asynchrone basé sur Redis.

    Features:
    - Stockage de données avec TTL
    - Invalidation par pattern
    - Support de la compression (optionnel)
    - Fallback silencieux si Redis est indisponible
    """

    def __init__(self, redis_url: str | None = None, default_ttl: int = 300):
        """Initialise le cache.

        Args:
            redis_url: URL de connexion Redis (défaut: config)
            default_ttl: TTL par défaut en secondes (défaut: 300)
        """
        self.default_ttl = default_ttl
        self._redis = None
        self._enabled = settings.redis_enabled and redis is not None

        if self._enabled:
            self._redis_url = redis_url or settings.redis_url
            self._connected = False
        else:
            self._redis_url = None
            self._connected = False

        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
        }

    async def _get_redis(self):
        """Obtient ou crée la connexion Redis."""
        if not self._enabled:
            return None

        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # Tester la connexion
                await self._redis.ping()
                self._connected = True
                logger.info("✅ Redis connected successfully")
            except Exception as e:
                logger.error(f"❌ Redis connection failed: {e}")
                self._connected = False
                return None

        return self._redis

    async def get(self, key: str, default: Any = None) -> Any | None:
        """Récupère une valeur du cache.

        Args:
            key: Clé du cache
            default: Valeur par défaut si la clé n'existe pas

        Returns:
            La valeur stockée ou la valeur par défaut
        """
        try:
            r = await self._get_redis()
            if r is None:
                return default

            data = await r.get(key)
            if data:
                self._stats["hits"] += 1
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    # Si ce n'est pas du JSON, retourner la valeur brute
                    logger.warning(f"⚠️ Invalid JSON for key: {key}")
                    return data

            self._stats["misses"] += 1
            return default

        except Exception as e:
            logger.error(f"❌ Cache get error: {e}")
            self._stats["errors"] += 1
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        compress: bool = False
    ) -> bool:
        """Stocke une valeur dans le cache.

        Args:
            key: Clé du cache
            value: Valeur à stocker
            ttl: Durée de vie en secondes (défaut: default_ttl)
            compress: Compresser la valeur (défaut: False)

        Returns:
            True si le stockage a réussi
        """
        try:
            r = await self._get_redis()
            if r is None:
                return False

            # Sérialiser la valeur
            try:
                data = json.dumps(value, default=str, ensure_ascii=False)
            except TypeError as e:
                logger.error(f"❌ Serialization error for key {key}: {e}")
                return False

            # Compresser si demandé
            if compress:
                try:
                    import zlib
                    data = zlib.compress(data.encode('utf-8'))
                except ImportError:
                    logger.warning("⚠️ zlib not available, skipping compression")

            await r.setex(
                key,
                ttl or self.default_ttl,
                data
            )
            self._stats["sets"] += 1
            return True

        except Exception as e:
            logger.error(f"❌ Cache set error: {e}")
            self._stats["errors"] += 1
            return False

    async def delete(self, key: str) -> bool:
        """Supprime une clé du cache.

        Args:
            key: Clé à supprimer

        Returns:
            True si la suppression a réussi
        """
        try:
            r = await self._get_redis()
            if r is None:
                return False

            result = await r.delete(key)
            if result > 0:
                self._stats["deletes"] += 1
            return True

        except Exception as e:
            logger.error(f"❌ Cache delete error: {e}")
            self._stats["errors"] += 1
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalide toutes les clés correspondant à un pattern.

        Args:
            pattern: Pattern de recherche (ex: "user:*")

        Returns:
            Nombre de clés supprimées
        """
        try:
            r = await self._get_redis()
            if r is None:
                return 0

            keys = await r.keys(pattern)
            if keys:
                deleted = await r.delete(*keys)
                self._stats["deletes"] += deleted
                logger.debug(f"🗑️ Invalidated {deleted} keys matching pattern: {pattern}")
                return deleted

            return 0

        except Exception as e:
            logger.error(f"❌ Cache invalidate pattern error: {e}")
            self._stats["errors"] += 1
            return 0

    async def exists(self, key: str) -> bool:
        """Vérifie si une clé existe dans le cache.

        Args:
            key: Clé à vérifier

        Returns:
            True si la clé existe
        """
        try:
            r = await self._get_redis()
            if r is None:
                return False

            return await r.exists(key) > 0

        except Exception as e:
            logger.error(f"❌ Cache exists error: {e}")
            return False

    async def increment(self, key: str, amount: int = 1) -> int | None:
        """Incrémente une valeur numérique.

        Args:
            key: Clé du compteur
            amount: Montant de l'incrémentation

        Returns:
            La nouvelle valeur ou None en cas d'erreur
        """
        try:
            r = await self._get_redis()
            if r is None:
                return None

            return await r.incrby(key, amount)

        except Exception as e:
            logger.error(f"❌ Cache increment error: {e}")
            self._stats["errors"] += 1
            return None

    async def clear(self) -> int:
        """Vide tout le cache.

        Returns:
            Nombre de clés supprimées
        """
        return await self.invalidate_pattern("*")

    async def get_stats(self) -> dict:
        """Retourne les statistiques du cache.

        Returns:
            Dictionnaire des statistiques
        """
        return {
            **self._stats,
            "enabled": self._enabled,
            "connected": self._connected,
            "redis_url": self._redis_url,
            "default_ttl": self.default_ttl,
        }

    async def close(self) -> None:
        """Ferme la connexion Redis."""
        if self._redis:
            try:
                await self._redis.close()
                logger.info("🔌 Redis connection closed")
            except Exception as e:
                logger.error(f"❌ Error closing Redis connection: {e}")


# Instance globale
cache = AsyncCache()


# ==========================================================
# Fonctions utilitaires
# ==========================================================

def cache_key(prefix: str, *args, **kwargs) -> str:
    """Génère une clé de cache formatée.

    Exemple:
        cache_key("user", id=123) -> "user:123"
        cache_key("stats", "admin", period="daily") -> "stats:admin:daily"

    Args:
        prefix: Préfixe de la clé
        *args: Arguments positionnels
        **kwargs: Arguments nommés

    Returns:
        Clé formatée
    """
    parts = [prefix]

    # Ajouter les arguments positionnels
    for arg in args:
        if arg is not None:
            parts.append(str(arg))

    # Ajouter les arguments nommés
    for key, value in sorted(kwargs.items()):
        if value is not None:
            parts.append(f"{key}:{value}")

    return ":".join(parts)


async def cached(
    key: str,
    func,
    ttl: int | None = None,
    *args,
    **kwargs
) -> Any:
    """Décorateur/utilitaire pour mettre en cache le résultat d'une fonction.

    Usage:
        result = await cached("user:123", get_user, user_id=123)

    Args:
        key: Clé du cache
        func: Fonction à appeler si le cache est vide
        ttl: TTL personnalisé
        *args: Arguments de la fonction
        **kwargs: Arguments nommés de la fonction

    Returns:
        Le résultat de la fonction (caché ou non)
    """
    # Vérifier le cache
    cached_value = await cache.get(key)
    if cached_value is not None:
        return cached_value

    # Appeler la fonction
    result = func(*args, **kwargs)

    # Si c'est un coroutine, l'attendre
    if hasattr(result, "__await__"):
        result = await result

    # Mettre en cache
    await cache.set(key, result, ttl=ttl)

    return result
