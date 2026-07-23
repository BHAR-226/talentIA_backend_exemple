"""Sonde de santé (liveness/readiness) — ne dépend pas de la base pour rester
verte même si la DB est momentanément indisponible."""

from fastapi import APIRouter

from app.core.responses import success

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Endpoint de health check pour vérifier que l'API est opérationnelle.

    Returns:
        dict: Statut "ok" si l'API est en ligne.
    """
    return success({"status": "ok"}, message="API opérationnelle")


@router.get("/health/ready")
def readiness() -> dict:
    """Endpoint de readiness check - vérifie que l'API est prête à servir.

    Returns:
        dict: Statut "ready" si l'API est prête.
    """
    # Ici on pourrait ajouter des vérifications supplémentaires
    # comme la connexion à la DB, Redis, etc.
    return success({"status": "ready"}, message="API prête à servir")


@router.get("/health/live")
def liveness() -> dict:
    """Endpoint de liveness check - vérifie que l'API est en vie.

    Returns:
        dict: Statut "alive" si l'API est en vie.
    """
    return success({"status": "alive"}, message="API en vie")
